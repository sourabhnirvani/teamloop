"""Run the TeamLoop server: python -m teamloop"""

import logging

import uvicorn

from teamloop import config
from teamloop.server.app import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(), host="127.0.0.1", port=config.port(), log_level="info")


if __name__ == "__main__":
    main()
