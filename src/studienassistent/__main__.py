"""Start the study assistant: python -m studienassistent --port 8100"""

import argparse
import sys
import tomllib
from importlib import resources
from pathlib import Path

import uvicorn

from chatsec.llm import ModelUnavailable, OpenAICompatibleModel, load_model_config
from studienassistent.app import create_app


def _default_port() -> int:
    text = (resources.files("studienassistent") / "data" / "settings.toml").read_text("utf-8")
    return int(tomllib.loads(text)["port"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="studienassistent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=_default_port())
    parser.add_argument("--config", default="config/models.toml")
    args = parser.parse_args(argv)

    spec = load_model_config(Path(args.config))["assistant"]
    model = OpenAICompatibleModel(
        spec.base_url, spec.model, reasoning_effort=spec.reasoning_effort
    )
    try:
        model.check_available()
    except ModelUnavailable as error:
        print(str(error), file=sys.stderr)
        return 2
    uvicorn.run(create_app(model), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
