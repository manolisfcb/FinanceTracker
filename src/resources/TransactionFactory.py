
from .NuTransactions import NuTransaction
class TransactionFactory():
    def __init__(self):
        pass
    
    def create_transaction(self, transaction_type):
        if transaction_type in allowed_banks:
            return allowed_banks[transaction_type]
        else:
            raise ValueError('Transaction type not allowed yet please add it to the allowed_banks list')
        
allowed_banks = {
    'Nu': NuTransaction
}