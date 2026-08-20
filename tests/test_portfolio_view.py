from datetime import date, datetime, timedelta
from unittest.mock import patch

from src.models import (
    Account,
    AccountType,
    AllocationTarget,
    Asset,
    DividendReceived,
    Fundamentals,
    FxRate,
    OrderModel,
    OrderType,
    PortfolioPlan,
    PortfolioSnapshotModel,
)


def _account(db, user, kind=AccountType.TFSA, name='TFSA Questrade'):
    account = Account(user_id=user.id, type=kind, name=name)
    db.session.add(account)
    db.session.commit()
    return account


def _position(db, user, account, symbol='RY', exchange='TSX', currency='CAD',
              quantity=42, cost=148.20, price=178.42, dividends=512.0,
              sector='Financial Services'):
    asset = Asset(symbol=symbol, yahoo_symbol=symbol, exchange=exchange,
                  currency=currency, name=f'{symbol} Inc', sector=sector)
    db.session.add(asset)
    db.session.commit()
    db.session.add(Fundamentals(asset_id=asset.id, as_of_date=date.today(), price=price))
    db.session.add(OrderModel(
        user_id=user.id, asset_id=asset.id, account_id=account.id, type=OrderType.BUY,
        quantity=quantity, price=cost, fees=0.0, currency=currency,
        fx_rate_to_cad=1.0, executed_at=datetime(2024, 3, 1),
    ))
    if dividends:
        db.session.add(DividendReceived(
            user_id=user.id, asset_id=asset.id, pay_date=date(2026, 6, 1),
            quantity_held=quantity, total_amount=dividends, currency='CAD', confirmed=True,
        ))
    db.session.commit()
    return asset


def test_portfolio_empty_state(auth_client, db, user):
    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'Todavía no tienes activos en tu portafolio.' in body


def test_position_row_shows_account_badge_and_yield_on_cost(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account)

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'class="acct"' in body
    assert 'TFSA' in body
    assert 'RY' in body
    # YoC = 512 / (42 * 148.20) = 8.23%
    assert '8.23%' in body


def test_asset_held_in_two_accounts_gets_a_badge_per_account(auth_client, db, user):
    """Positions are pooled per asset, so the second account has to show up as
    a second chip rather than silently disappearing."""
    tfsa = _account(db, user, AccountType.TFSA, 'TFSA')
    rrsp = _account(db, user, AccountType.RRSP, 'RRSP')
    asset = _position(db, user, tfsa, dividends=0)
    db.session.add(OrderModel(
        user_id=user.id, asset_id=asset.id, account_id=rrsp.id, type=OrderType.BUY,
        quantity=10, price=150.0, fees=0.0, currency='CAD',
        fx_rate_to_cad=1.0, executed_at=datetime(2024, 4, 1),
    ))
    db.session.commit()

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert body.count('class="acct"') == 2


def test_headline_return_counts_dividends_and_realized_trades(auth_client, db, user):
    account = _account(db, user)
    # 10 shares at 100 = 1000 cost, now worth 1200, plus 100 of dividends.
    _position(db, user, account, quantity=10, cost=100.0, price=120.0, dividends=100.0)

    body = auth_client.get('/portfolio').get_data(as_text=True)

    # (200 unrealized + 100 dividends) / 1000
    assert '+30.00%' in body


def test_plan_vs_real_renders_a_bar_per_sector_target(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account, quantity=10, cost=100.0, price=100.0, dividends=0,
              sector='Financial Services')
    db.session.add(AllocationTarget(user_id=user.id, sector='Financial Services', target_percent=60.0))
    db.session.commit()

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'Plan vs. real' in body
    assert 'tn-bar-target' in body
    assert 'Financial Services' in body
    assert 'meta 60.00%' in body
    # Sole sector, so it's 100% of the book against a 60% target: 40 points over.
    assert 'Mayor desvío' in body
    assert '+40.00 pt' in body


def test_plan_vs_real_pools_every_holding_in_the_same_sector(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account, symbol='RY', quantity=10, cost=100.0, price=100.0,
              dividends=0, sector='Financial Services')
    _position(db, user, account, symbol='TD', quantity=10, cost=100.0, price=100.0,
              dividends=0, sector='Financial Services')
    db.session.add(AllocationTarget(user_id=user.id, sector='Financial Services', target_percent=100.0))
    db.session.commit()

    body = auth_client.get('/portfolio').get_data(as_text=True)

    # Two names, one bar — the plan is about the sector, not the tickers.
    assert body.count('tn-bar-target') == 1
    assert 'meta 100.00%' in body


def test_a_held_sector_without_a_target_is_shown_at_meta_none(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account, symbol='RY', quantity=10, cost=100.0, price=100.0,
              dividends=0, sector='Financial Services')
    _position(db, user, account, symbol='ENB', quantity=10, cost=100.0, price=100.0,
              dividends=0, sector='Energy')
    db.session.add(AllocationTarget(user_id=user.id, sector='Financial Services', target_percent=100.0))
    db.session.commit()

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'Energy' in body
    assert 'meta —' in body


def test_setting_a_sector_target_saves_and_redirects(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account, sector='Energy', dividends=0)

    response = auth_client.post(
        '/portfolio/allocation-targets',
        data={'sector': 'Energy', 'target_percent': '25'},
    )

    assert response.status_code == 302
    target = AllocationTarget.query.filter_by(user_id=user.id, sector='Energy').one()
    assert target.target_percent == 25.0


def test_footnote_shows_the_usd_rate_at_four_decimals(auth_client, db, user):
    """Two decimals collapse 1.3642 and 1.3598 into the same number, and the
    CAD totals stop reconciling against it."""
    account = _account(db, user)
    _position(db, user, account)
    db.session.add(FxRate(date=date.today(), pair='USDCAD', rate=1.3642))
    db.session.commit()

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert '1.3642' in body


def test_whole_share_counts_render_without_decimals(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account, quantity=208, dividends=0)

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert '>208</td>' in body
    assert '208.00' not in body


def test_fractional_share_counts_render_with_four_decimals(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account, quantity=0.2254, dividends=0)

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert '>0.2254</td>' in body


def test_portfolio_ideal_has_no_mock_targets_before_user_configures_it(auth_client, db, user):
    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'Tu portafolio ideal' in body
    assert 'Todavía no configuraste un portafolio ideal.' in body
    assert 'groupedAllocationChart' not in body
    assert 'Rentabilidad comparada' in body
    assert 'Composición por tipo y segmento' in body
    assert 'Dividendos por activo' in body
    assert 'Renta fija' in body
    assert 'value="40.00"' not in body
    assert 'value="30.00"' not in body


def test_user_can_save_a_complete_portfolio_plan(auth_client, db, user):
    response = auth_client.post('/portfolio/plan', data={
        'equity_etf_percent': '35',
        'reit_percent': '25',
        'fixed_income_percent': '10',
        'crypto_percent': '20',
        'cash_percent': '10',
        'cash_balance_cad': '2500',
    })

    assert response.status_code == 302
    plan = PortfolioPlan.query.filter_by(user_id=user.id).one()
    assert plan.equity_etf_percent == 35.0
    assert plan.fixed_income_percent == 10.0
    assert plan.cash_balance_cad == 2500.0


def test_portfolio_plan_must_sum_to_one_hundred(auth_client, db, user):
    response = auth_client.post('/portfolio/plan', data={
        'equity_etf_percent': '40',
        'reit_percent': '30',
        'fixed_income_percent': '0',
        'crypto_percent': '20',
        'cash_percent': '20',
        'cash_balance_cad': '0',
    }, follow_redirects=True)

    assert 'debe sumar exactamente 100%' in response.get_data(as_text=True)
    assert PortfolioPlan.query.filter_by(user_id=user.id).first() is None


def test_current_allocation_uses_persisted_reit_crypto_fixed_income_and_cash_categories(
    auth_client, db, user
):
    tfsa = _account(db, user)
    crypto_account = _account(db, user, AccountType.CRYPTO, 'Crypto')
    reit = _position(
        db, user, tfsa, symbol='REI.UN', quantity=10, cost=20, price=25,
        dividends=0, sector='Real Estate',
    )
    reit.industry = 'REIT - Retail'
    reit.category = 'REIT'
    _position(
        db, user, crypto_account, symbol='BTC', exchange='CRYPTO', quantity=1,
        cost=100, price=200, dividends=0, sector='Cryptoassets',
    )
    _position(
        db, user, tfsa, symbol='GOC30', exchange='OTC', quantity=1,
        cost=100, price=100, dividends=0, sector='Fixed Income',
    )
    db.session.add(PortfolioPlan(
        user_id=user.id, equity_etf_percent=30, reit_percent=30,
        fixed_income_percent=10, crypto_percent=20, cash_percent=10,
        cash_balance_cad=50,
    ))
    db.session.commit()

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'currentAllocationChart' in body
    assert 'REIT - Retail' not in body
    assert 'Retail \\u00b7 REITs' in body
    assert 'Efectivo CAD' in body
    assert '"classKey": "CRYPTO"' in body
    assert '"classKey": "FIXED_INCOME"' in body


def test_dividend_chart_includes_total_and_per_share(auth_client, db, user):
    account = _account(db, user)
    _position(db, user, account, quantity=10, dividends=50)

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'dividendsByAssetChart' in body
    assert '"received_cad": 50.0' in body
    assert '"per_share_cad": 5.0' in body


@patch('src.services.portfolio_analytics._canadian_policy_rate_return')
@patch('src.services.portfolio_analytics.get_provider')
def test_performance_chart_compares_portfolio_with_canadian_benchmarks(
    mock_get_provider, mock_policy_rate, auth_client, db, user
):
    first_day = date.today() - timedelta(days=10)
    db.session.add_all([
        PortfolioSnapshotModel(
            user_id=user.id, account_id=None, date=first_day,
            patrimony_cad=1000, total_invested_cad=1000, dividends_accum_cad=0,
        ),
        PortfolioSnapshotModel(
            user_id=user.id, account_id=None, date=date.today(),
            patrimony_cad=1100, total_invested_cad=1000, dividends_accum_cad=0,
        ),
    ])
    db.session.commit()
    mock_get_provider.return_value.get_price_history.return_value = [
        {'date': first_day.isoformat(), 'close': 100.0},
        {'date': date.today().isoformat(), 'close': 105.0},
    ]
    mock_policy_rate.return_value = {
        first_day.isoformat(): 0.0,
        date.today().isoformat(): 0.06,
    }

    body = auth_client.get('/portfolio').get_data(as_text=True)

    assert 'performanceComparisonChart' in body
    assert 'S\\u0026P/TSX (XIC)' in body
    assert 'Tasa BoC acumulada' in body
    assert mock_get_provider.return_value.get_price_history.call_count == 3
