"""Filing finished generations into a demo project, which everyone sees (app.sharing), so a new account has
something to look at and reuse before it has made anything.

    uv run python -m app.demo krea2-turbo flux2-klein-edit minimax-h3
    uv run python -m app.demo minimax-h3 --name "Demo videos"

Every finished generation of the pipelines named moves into the project, which is made if there's none by that name
yet. They must all have one owner, who then owns the project and is the only one who can add to it.
"""

import argparse
import sys

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import make_engine
from app.models import Generation, GenerationStatus, Project
from app.settings import Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.demo", description="File generations into a demo project")
    parser.add_argument("pipelines", nargs="+", help="pipeline ids, such as krea2-turbo")
    parser.add_argument("--name", default="Demo", help="the project's name (default: Demo)")
    args = parser.parse_args(argv)

    with Session(make_engine(Settings().database_url)) as session:
        finished = (Generation.pipeline_id.in_(args.pipelines), Generation.status == GenerationStatus.DONE)
        owners = session.scalars(select(Generation.owner_id).where(*finished).distinct()).all()
        if not owners:
            sys.exit(f"No finished generations from {', '.join(args.pipelines)}")
        if len(owners) > 1:
            sys.exit("Those generations belong to more than one account; a project has one owner")
        owner = owners[0]
        project = session.scalars(select(Project).where(Project.owner_id == owner, Project.name == args.name)).first()
        if project is None:
            project = Project(owner_id=owner, name=args.name)
            session.add(project)
        project.is_demo = True
        session.flush()
        moved = session.scalar(select(func.count()).where(*finished))
        session.execute(update(Generation).where(*finished).values(project_id=project.id))
        session.commit()
    print(f"{moved} generations are in the demo project {args.name!r}")


if __name__ == "__main__":
    main()
