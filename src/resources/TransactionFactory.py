
from csv import DictReader
from .NuTransactions import NuTransaction
class TransactionFactory():
    def __init__(self, transaction_csv: DictReader, bank_name: str):
        self.transaction_csv = transaction_csv
        self.bank_name = bank_name
        
    
    def create_transaction(self):
        if self.bank_name in allowed_banks:
            return allowed_banks[self.bank_name].convert_to_transaction(self.transaction_csv)
        else:
            raise ValueError('Transaction type not allowed yet please add it to the allowed_banks list')
        
allowed_banks = {
    'Nu': NuTransaction
}