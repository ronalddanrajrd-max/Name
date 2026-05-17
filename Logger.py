import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("OkveHUB")

def info(msg): log.info(f"  {msg}")
def success(msg): log.info(f"✅ {msg}")
def warn(msg): log.warning(f"⚠️  {msg}")
def error(msg): log.error(f"❌ {msg}")
def cmd(msg): log.info(f"⚡ {msg}")
def event(msg): log.info(f"📡 {msg}")
