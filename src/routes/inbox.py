from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from src.extensions import db
from src.models import Asset, CompanyEvent, CompanyEventKind, CompanyEventRead, OrderModel

inbox_bp = Blueprint('inbox', __name__)

KIND_FILTERS = [
    (None, 'Todos'),
    (CompanyEventKind.DIVIDEND, 'Dividendos'),
    (CompanyEventKind.EARNINGS, 'Resultados'),
    (CompanyEventKind.FILING, 'Filings'),
    (CompanyEventKind.NEWS, 'Noticias'),
]

_RELATIVE_DAYS = {0: 'Hoy', 1: 'Ayer'}


def _held_asset_ids(user_id):
    return {
        row[0]
        for row in OrderModel.query.with_entities(OrderModel.asset_id)
        .filter_by(user_id=user_id)
        .distinct()
        .all()
    }


def _events_query(user_id):
    asset_ids = _held_asset_ids(user_id)
    if not asset_ids:
        return None
    return CompanyEvent.query.filter(CompanyEvent.asset_id.in_(asset_ids))


def unread_inbox_count(user_id) -> int:
    query = _events_query(user_id)
    if query is None:
        return 0
    read_ids = {
        row[0]
        for row in CompanyEventRead.query.with_entities(CompanyEventRead.company_event_id)
        .filter_by(user_id=user_id)
        .all()
    }
    if read_ids:
        query = query.filter(~CompanyEvent.id.in_(read_ids))
    return query.count()


def _relative_day(day: date) -> str | None:
    return _RELATIVE_DAYS.get((date.today() - day).days)


def _grouped_events(user_id, kind):
    query = _events_query(user_id)
    if query is None:
        return []
    if kind is not None:
        query = query.filter(CompanyEvent.kind == kind)

    events = query.order_by(CompanyEvent.published_at.desc()).limit(100).all()
    if not events:
        return []

    assets = {
        a.id: a
        for a in Asset.query.filter(Asset.id.in_({e.asset_id for e in events})).all()
    }
    read_ids = {
        row[0]
        for row in CompanyEventRead.query.with_entities(CompanyEventRead.company_event_id)
        .filter_by(user_id=user_id)
        .all()
    }

    groups = []
    for event in events:
        day = event.published_at.date()
        if not groups or groups[-1]['day'] != day:
            groups.append({'day': day, 'relative': _relative_day(day), 'events': []})
        groups[-1]['events'].append({
            'id': event.id,
            'kind': event.kind,
            'source': event.source,
            'title': event.title,
            'summary': event.summary,
            'url': event.url,
            'published_at': event.published_at,
            'event_date': event.event_date,
            'asset': assets.get(event.asset_id),
            'read': event.id in read_ids,
        })
    return groups


@inbox_bp.route('/inbox', methods=['GET'])
@login_required
def inbox_page():
    kind_arg = request.args.get('kind')
    kind = next((k for k, _ in KIND_FILTERS if k is not None and k.value == kind_arg), None)

    context = {
        'groups': _grouped_events(current_user.id, kind),
        'kind_filters': KIND_FILTERS,
        'selected_kind': kind,
    }
    if request.headers.get('HX-Request'):
        return render_template('partials/inbox_timeline.html', **context)
    return render_template('inbox.html', **context)


@inbox_bp.route('/inbox/<int:event_id>/read', methods=['POST'])
@login_required
def mark_read(event_id):
    query = _events_query(current_user.id)
    if query is None or query.filter(CompanyEvent.id == event_id).first() is None:
        return {'message': 'Event not found'}, 404

    existing = CompanyEventRead.query.filter_by(
        user_id=current_user.id, company_event_id=event_id
    ).first()
    if existing is None:
        db.session.add(
            CompanyEventRead(
                user_id=current_user.id,
                company_event_id=event_id,
                read_at=datetime.utcnow(),
            )
        )
        db.session.commit()
    return '', 204


@inbox_bp.route('/inbox/read-all', methods=['POST'])
@login_required
def mark_all_read():
    query = _events_query(current_user.id)
    if query is not None:
        read_ids = {
            row[0]
            for row in CompanyEventRead.query.with_entities(CompanyEventRead.company_event_id)
            .filter_by(user_id=current_user.id)
            .all()
        }
        now = datetime.utcnow()
        for event in query.all():
            if event.id not in read_ids:
                db.session.add(
                    CompanyEventRead(
                        user_id=current_user.id, company_event_id=event.id, read_at=now
                    )
                )
        db.session.commit()

    if request.headers.get('HX-Request'):
        return '', 204
    flash('Todo marcado como leído', 'success')
    return redirect(url_for('inbox.inbox_page'))
