from sqlalchemy import and_, case, func
from src.models.Transaction import TransactionModel, TransactionType


def filter(model, filter, relation=None):
    """
    Function to filter a model with a dictionary
    :param model: Model to filter
    :param filter: Dictionary with the filters
    :param relation: Relation to filter
    :return: Query with the filters
    """
    query = model.query
    for key, value in filter.items():
        if hasattr(model, key):
            column = getattr(model, key)
            if isinstance(value, dict):
                conditions = []
                if 'gte' in value:
                    conditions.append(getattr(model, key) >= value['gte'])
                if 'lte' in value:
                    conditions.append(getattr(model, key) <= value['lte'])
                if 'eq' in value:
                    conditions.append(getattr(model, key) == value['eq'])
                if 'ne' in value:
                    conditions.append(getattr(model, key) != value['ne'])
                query = query.filter(and_(*conditions))
            else:
                query = query.filter(column == value)
        elif relation and hasattr(relation, key):
            rel_model = relation[key]
            query = query.join(rel_model).filter(rel_model.name == value)
            
    return query

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