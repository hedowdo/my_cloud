"""Interactive, local first-administrator bootstrap. Passwords never enter command arguments."""

import getpass
import sys

from pydantic import ValidationError

from app.config import Settings
from app.database import make_engine
from app.identity_security import AccountInput, AuthError
from app.identity_service import Identity


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Run interactively in a terminal; redirected passwords are refused")
    settings = Settings()
    engine = make_engine(settings)
    try:
        email = input("Administrator email: ")
        password = getpass.getpass("New password (12–128 characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("Passwords did not match; no account created")
        try:
            data = AccountInput(email=email, password=password)
        except ValidationError:
            raise SystemExit("Enter a valid email and a 12–128 character password") from None
        Identity(engine, settings).bootstrap(str(data.email), data.password.get_secret_value())
        print("First administrator created. Sign in through the browser.")
    except AuthError as exc:
        raise SystemExit(exc.message) from None
    except (EOFError, KeyboardInterrupt):
        raise SystemExit("Canceled; no account created") from None
    except Exception:
        raise SystemExit("Bootstrap failed; verify configuration and database readiness") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
