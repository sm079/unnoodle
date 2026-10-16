"""Managing accounts from the command line, for what the app itself doesn't offer: making the first admin, and
resetting a forgotten password while there's no email to send a reset link with.

    uv run python -m app.users create someone@example.com --admin
    uv run python -m app.users set-password someone@example.com
    uv run python -m app.users admin someone@example.com [--remove]

The password is asked for, or read from standard input when that isn't a terminal. Setting one signs the account out
everywhere.
"""

import argparse
import getpass
import sys

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.accounts import MIN_PASSWORD, Email, hash_password
from app.db import make_engine
from app.models import User, UserSession
from app.settings import Settings


def read_password() -> str:
    if sys.stdin.isatty():
        password = getpass.getpass("Password: ")
        if getpass.getpass("Again: ") != password:
            sys.exit("The passwords don't match")
    else:
        # Windows shells end a piped line with \r\n, and the \r would become part of the password
        password = sys.stdin.readline().rstrip("\r\n")
    if len(password) < MIN_PASSWORD:
        sys.exit(f"Passwords need at least {MIN_PASSWORD} characters")
    return password


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.users", description="Manage accounts")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="make an account")
    create.add_argument("email")
    create.add_argument("--admin", action="store_true", help="let it change settings that affect everyone")
    commands.add_parser("set-password", help="set an account's password").add_argument("email")
    admin = commands.add_parser("admin", help="make an account an admin")
    admin.add_argument("email")
    admin.add_argument("--remove", action="store_true", help="make it an ordinary account again")
    args = parser.parse_args(argv)

    try:
        email = TypeAdapter(Email).validate_python(args.email)
    except ValidationError:
        sys.exit(f"{args.email} doesn't look like an email address")

    with Session(make_engine(Settings().database_url)) as session:
        user = session.scalars(select(User).where(User.email == email)).first()
        if args.command == "create":
            if user is not None:
                sys.exit(f"There's already an account for {email}")
            session.add(User(email=email, password_hash=hash_password(read_password()), is_admin=args.admin))
        elif user is None:
            sys.exit(f"There's no account for {email}")
        elif args.command == "set-password":
            user.password_hash = hash_password(read_password())
            session.execute(delete(UserSession).where(UserSession.user_id == user.id))
        else:
            user.is_admin = not args.remove
        session.commit()
    print("Done")


if __name__ == "__main__":
    main()
