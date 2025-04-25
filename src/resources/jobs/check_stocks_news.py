from utils.brfinance import CVMAsyncBackend
from models import StockModel
from app import db, scheduler
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import os
from dataclasses import dataclass





