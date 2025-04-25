from flask_restful import Resource
from flask import request
from flask_login import current_user
import pandas as pd
from app import db
from src.models import StockModel, OrderModel
from src.resources.OrdersFactory import Orders, OrdersFromB3
from src.resources.PortfolioFactory import Portfolio, PortfolioByTransaction, PortfolioByPosition
class StockResources(Resource):
    def get(self):
        reqst = request.args
        print(reqst)
        return {'hello': 'world'}
    
    def post(self):
        rq = request.form
        print(rq)
        
        return {'hello': 'world'}
    
    def put(self):
        return {'hello': 'world'}
    
    def delete(self):   
        return {'hello': 'world'}
    


class UploadPortfolio(Resource):
    def post(self):
        # Verifica si el archivo está presente
        if 'file' not in request.files:
            return {"error": "No file part"}, 400
        file = request.files['file']
        file_type = request.form['file_type']
        # Verifica si se seleccionó un archivo
        if file.filename == '':
            return {"error": "No selected file"}, 400
        
        # Procesar el archivo
        try:
            user_id = current_user.id
            new_df = pd.read_excel(file)  # Leer el archivo con pandas
            
            orderstrategy = OrdersFromB3()
            orders = Orders(orderstrategy, new_df)
            orders_to_db = orders.create_orders()
            orders_to_db["user_id"] = user_id
            orders_to_db.to_sql('orders', con=db.engine, if_exists='append', index=False)
            if request.form['file_type'] == 'mov':
                portfoliostrategy = PortfolioByTransaction()
            else:
                portfoliostrategy = PortfolioByPosition()
            
            portfolio = Portfolio(portfoliostrategy, orders_to_db, user_id)
            portfolio.portfolio_df.to_sql('portfolios', con=db.engine, if_exists='append', index=False)
            return portfolio.portfolio_df.to_dict(orient='records'), 200
        except Exception as e:
            return {"error": f"Failed to process file: {str(e)}"}, 500
        #     new_df['Data do Negócio'] = new_df.apply(get_date, axis=1)
        #     new_df['Tipo de Movimentação'] = new_df.apply(get_type_of_negotiation, axis=1)
        #     new_df['Código de Negociação'] = new_df.apply(get_symbol, axis=1)
        #     new_df['user_id'] = user_id
        #     new_df.rename(columns={'Preço': 'price', 'Quantidade': 'quantity', 'Data do Negócio': 'negociation_date', 'Tipo de Movimentação': 'type_of_negotiation', 'Código de Negociação': 'symbol'}, inplace=True)
        #     new_df.to_sql('stocks', con=db.engine, if_exists='append', index=False)
        
            
        #     return {"message": "File uploaded successfully", "columns": new_df.columns.tolist()}, 200
        # except Exception as e:
        #     return {"error": f"Failed to process file: {str(e)}"}, 500



def get_date(row):
    date = row["Data do Negócio"]
    return pd.to_datetime(date, format='%d/%m/%Y')



def get_type_of_negotiation(row):
    if row["Tipo de Movimentação"] == "Compra":
        return "BUY"
    return "SELL"
    
def get_symbol(row):
    return row['Código de Negociação']

def get_cvm_code(symbol, cvm_codes):
    try:
        symbol = symbol[0:4]
        return cvm_codes[cvm_codes['base_symbol'] == symbol]['cvm_code'].values[0]
    except:
        return None
