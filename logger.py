import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename=f'logs/{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'
    )
logger = logging.getLogger(__name__)