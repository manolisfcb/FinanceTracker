from .TransactionsBase import TransactionBase
import csv
from datetime import datetime
from src.models.Transaction import TransactionModel, Category, TransactionType

class NuTransaction(TransactionBase):
    def convert_to_transaction(csv_reader: csv.DictReader):
        try:
            transactions = []
            for row in csv_reader:
                category = get_category(row)
                amount = float(row['Valor'])
                type = get_type(amount)
                description = row['Descrição']
                date = convert_string_to_date(row['Data'])
                transaction = {
                    'category': category,
                    'amount': amount,
                    'type': type,
                    'description': description,
                    'date': date
                }
                transactions.append(transaction)
        except Exception as e:
            raise ValueError(f'CSV file not match with Nubank models. Expected columns: Valor, Descrição, Data. Error: {e} not found')
        return transactions
            
            
    
    
def get_category(row):
    
    #TODO: Crear funcion para identificar categoria por la descripcion de la transaccion
    # De momento se retorna Bill
    # category = Category.query.filter_by(name=row['category']).first()
    # if not category:
    #     category = Category(name=row['category'])
    #     category.save()
    category = Category.query.filter_by(name='Bills').first()
    return category          

def get_type(amount):
    if amount < 0:
        return TransactionType.EXPENSE
    else:
        return TransactionType.INCOME
        
    
def convert_string_to_date(date: str):
    return datetime.strptime(date, '%d/%m/%Y')
        

