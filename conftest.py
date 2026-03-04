import sys
import os
from pathlib import Path

# garante que a raiz do projeto está no sys.path
sys.path.insert(0, str(Path(__file__).parent))

# quando rodar fora do Docker, o host do postgres é localhost
# dentro do Docker, o compose injeta POSTGRES_HOST=postgres via .env
if not os.getenv("RUNNING_IN_DOCKER"):
    os.environ.setdefault("POSTGRES_HOST", "localhost")
