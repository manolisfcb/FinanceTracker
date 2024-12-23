import csv
from io import TextIOWrapper
from abc import ABC, abstractmethod



         
        

class TransactionBase(ABC):
    def __init__(self):
        self.category = None
        self.date = None
        self.amount = None
        self.type = None
        self.description = None
        
    @abstractmethod
    def set_category(self, category):
        pass
    
    @abstractmethod
    def set_date(self, date):
        pass
    
    @abstractmethod
    def set_amount(self, amount):
        pass
    
    @abstractmethod
    def set_type(self, type):
        pass
