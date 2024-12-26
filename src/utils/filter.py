from sqlalchemy import and_, case, func
from src.models.Transaction import TransactionModel, TransactionType


def filter(qs, filter, relation=None):
    """
    Function to filter a model with a dictionary
    :param model: Model to filter
    :param filter: Dictionary with the filters
    :param relation: Relation to filter
    :return: Query with the filters
    
    qs: QuerySet
    """
            # Aplicar filtros dinámicamente
    

def filter_by_columns_ilike(filters):
    output_filter = []
    for filter in filters:
        if filter['value']:
            column = getattr(filter['model'], filter['column'])
            if column is not None:
                output_filter.append(column.ilike(f"%{filter['value']}%"))
            else:
                continue
        else:
            continue
    return output_filter
            
    

def get_totals(query):
    # Calcular totales en una sola consulta

    totals = query.with_entities(
        func.sum(TransactionModel.amount).label('total_amount'),
        func.sum(
            case(
                (TransactionModel.type == TransactionType.INCOME, TransactionModel.amount),
                else_=0
            )
        ).label('total_income'),
        func.sum(
            case(
                (TransactionModel.type == TransactionType.EXPENSE, TransactionModel.amount),
                else_=0
            )
        ).label('total_expenses')
    ).first()

        # Extraer resultados de los agregados
    total_income = round(totals.total_income, 2) if totals.total_income else 0.0
    total_expenses = round(totals.total_expenses, 2) if totals.total_expenses else 0.0

    total_amount = total_income - total_expenses

    totals = {
        'total_amount': round(total_amount),
        'total_income': total_income,
        'total_expenses': total_expenses
    }
    return totals