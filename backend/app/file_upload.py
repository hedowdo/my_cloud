"""One metadata part followed by one streamed file, with bounded memory and durable intent."""

import hashlib
import logging
import os

from pydantic import ValidationError
from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header
from sqlalchemy import text

from app.file_models import FILE_LIMIT, UploadInput, fail
from app.file_service import advisory_key

logging.getLogger("python_multipart.multipart").setLevel(logging.CRITICAL)


class Upload:
    def __init__(self, files, session, csrf, request_id, content_type):
        kind, options = parse_options_header(content_type)
        boundary = options.get(b"boundary", b"")
        if kind != b"multipart/form-data" or not 1 <= len(boundary) <= 70:
            fail("multipart_required", "Send multipart metadata followed by one file", 415)
        self.files, self.session, self.csrf, self.request_id = files, session, csrf, request_id
        self.reservation = self.stream = self.lease = None
        self.parts, self.received, self.wire_bytes = 0, 0, 0
        self.metadata = bytearray()
        self.headers = {}
        self.header_name = self.header_value = b""
        self.header_bytes = 0
        self.ended = False
        self.hash = hashlib.sha256()
        self.parser = MultipartParser(
            boundary,
            {
                "on_part_begin": self.part_begin,
                "on_header_field": self.header_field,
                "on_header_value": self.header_value_data,
                "on_header_end": self.header_end,
                "on_headers_finished": self.headers_finished,
                "on_part_data": self.data,
                "on_part_end": self.part_end,
                "on_end": self.end,
            },
        )

    def part_begin(self):
        self.parts += 1
        if self.parts > 2:
            fail("invalid_multipart", "Send exactly one metadata part and one file", 422)
        self.headers = {}
        self.header_name = self.header_value = b""
        self.header_bytes = 0

    def add_header(self, data, start, end):
        self.header_bytes += end - start
        if self.header_bytes > 8192:
            fail("headers_too_large", "Upload part headers are too large", 413)
        return data[start:end]

    def header_field(self, data, start, end):
        self.header_name += self.add_header(data, start, end)

    def header_value_data(self, data, start, end):
        self.header_value += self.add_header(data, start, end)

    def header_end(self):
        name = self.header_name.lower()
        if name in self.headers or len(self.headers) >= 8:
            fail("invalid_multipart", "Invalid upload headers", 422)
        self.headers[name] = self.header_value
        self.header_name = self.header_value = b""

    def headers_finished(self):
        kind, options = parse_options_header(self.headers.get(b"content-disposition", b""))
        expected = b"metadata" if self.parts == 1 else b"file"
        if kind != b"form-data" or options.get(b"name") != expected:
            fail("invalid_multipart", "Send metadata before the file", 422)
        if self.parts == 1 and b"filename" in options:
            fail("invalid_multipart", "Metadata must be a JSON field", 422)
        if self.parts == 2:
            if not self.reservation or b"filename" not in options:
                fail("invalid_multipart", "A file part is required", 422)
            self.lease = self.files.engine.connect()
            self.lease.execute(
                text("SELECT pg_advisory_lock(:key)"),
                {"key": advisory_key(self.reservation["blob_id"])},
            )
            self.lease.commit()
            self.stream = self.files.store.create(self.reservation["key"])

    def data(self, data, start, end):
        chunk = data[start:end]
        if self.parts == 1:
            if len(self.metadata) + len(chunk) > 4096:
                fail("metadata_too_large", "Upload metadata is too large", 413)
            self.metadata.extend(chunk)
        else:
            self.write(chunk)

    def write(self, chunk):
        if not self.stream:
            fail("invalid_multipart", "File contents are missing", 422)
        if (
            self.received + len(chunk) > FILE_LIMIT
            or self.received + len(chunk) > self.reservation["size"]
        ):
            fail("file_too_large", "File exceeds its declared size or the 500 MB limit", 413)
        with self.files.engine.begin() as connection:
            # Serialize space checks and physical writes across API processes.
            connection.execute(text("SELECT pg_advisory_xact_lock(735104)"))
            if self.files.store.free() - len(chunk) < self.files.settings.storage_reserve_bytes:
                fail("disk_reserve", "Upload stopped to preserve emergency disk space", 507)
            written = self.stream.write(chunk)
            if written != len(chunk):
                raise OSError("Short storage write")
            self.received += len(chunk)
            self.hash.update(chunk)
            connection.execute(
                text("""UPDATE upload_reservations SET state='streaming',
                received_bytes=:received WHERE id=:id AND state IN ('reserved','streaming')"""),
                {"id": self.reservation["id"], "received": self.received},
            )

    def part_end(self):
        if self.parts == 1:
            try:
                intent = UploadInput.model_validate_json(self.metadata)
            except ValidationError:
                fail("invalid_request", "Check upload metadata and the 500 MB size limit", 422)
            self.reservation = self.files.reserve(self.session, self.csrf, intent, self.request_id)

    def end(self):
        self.ended = True

    def feed(self, chunk):
        self.wire_bytes += len(chunk)
        if self.wire_bytes > FILE_LIMIT + 32768:
            fail("file_too_large", "Upload exceeds the maximum request size", 413)
        self.parser.write(chunk)

    def finish(self):
        self.parser.finalize()
        if not self.ended or self.parts != 2 or not self.stream:
            fail("incomplete_upload", "The upload was interrupted or malformed", 422)
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        self.stream = None
        return self.files.finish(
            self.session, self.csrf, self.reservation, self.received, self.hash.hexdigest()
        )

    def close(self, success=False):
        if self.stream:
            self.stream.close()
            self.stream = None
        try:
            if self.reservation and not success:
                self.files.abandon(self.reservation)
        finally:
            if self.lease:
                try:
                    self.lease.execute(
                        text("SELECT pg_advisory_unlock(:key)"),
                        {"key": advisory_key(self.reservation["blob_id"])},
                    )
                    self.lease.commit()
                finally:
                    self.lease.close()
                    self.lease = None
