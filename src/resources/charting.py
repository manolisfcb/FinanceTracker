import plotly.express as px
from pandas import DataFrame


def plot_income_expense_bar_char(df: DataFrame):
    x_vals = ['Income', 'Expense']
    y_vals = [df[df['type'] == 'income']['amount'].sum(), df[df['type'] == 'expense']['amount'].sum()]
    fig = px.bar(x=x_vals, y=y_vals, labels={'x': 'Type', 'y': 'Amount'}, title='Income vs Expense') 
   
    return fig

def plot_category_pie_chart(df: DataFrame):
    fig = px.pie(df, names='category_id', values='amount', title=f'Category Distribution for {df.type.values[0]}')
    return fig