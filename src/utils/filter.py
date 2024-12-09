from sqlalchemy import and_


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