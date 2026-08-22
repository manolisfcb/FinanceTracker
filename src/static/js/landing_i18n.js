// Client-side language switcher for the public landing page. Swaps the text
// of every [data-i18n] node between es/en/pt and remembers the choice, so the
// server can keep rendering a single (Spanish) template.
(function () {
    var STORAGE_KEY = 'tn_lang';
    var SUPPORTED = ['es', 'en', 'pt'];
    var HTML_LANG = { es: 'es-CA', en: 'en-CA', pt: 'pt-BR' };

    var translations = {
        es: {
            'hero.title': 'Tu portafolio, con el análisis que le falta.',
            'hero.subtitle': 'Reuní todas tus cuentas de inversión en una sola cartera. TrueNorth calcula el costo base promedio de cada posición, sigue tus dividendos y te da los fundamentales de cada empresa que tenés.',
            'hero.cta_register': 'Crear cuenta gratis',
            'hero.cta_google': 'Continuar con Google',
            'hero.trust1': 'Gratis, sin tarjeta',
            'hero.trust2': 'Multi-moneda, con FX diario',
            'hero.trust3': 'Tus datos son solo tuyos',
            'card.total_equity': 'Patrimonio total',
            'card.contributed': 'Aportado',
            'card.dividends_12m': 'Dividendos 12m',
            'card.yield_on_cost': 'Yield on cost',
            'card.sector_plan': 'Plan por sector',
            'card.real_vs_target': 'real vs. objetivo',
            'card.sector_financial': 'Financiero',
            'card.sector_energy': 'Energía',
            'card.sector_tech': 'Tecnología',
            'card.th_asset': 'Activo',
            'card.th_avg_cost': 'Costo prom.',
            'card.th_value': 'Valor',
            'card.caption': 'Ejemplo ilustrativo de un dashboard, no son cifras reales.',
            'brokers.import_from': 'Importá tu historial desde',
            'brokers.manual': '…o cargá cada orden a mano en 20 segundos',
            'features.heading': 'Seis cosas que hoy hacés en cinco planillas',
            'features.subheading': 'Cada una vive acá, con los mismos datos y la misma moneda base.',
            'features.f1.title': 'Portafolio consolidado',
            'features.f1.desc': 'Todas tus cuentas en una sola cartera, o filtradas de a una. Posiciones, costo, valor de mercado y P&L, siempre en tu moneda base.',
            'features.f2.title': 'Costo base promedio (ACB)',
            'features.f2.desc': 'Costo promedio ponderado recalculado en cada compra, para que la ganancia de capital de una venta no sea una estimación.',
            'features.f3.title': 'Screener fundamental',
            'features.f3.desc': 'P/E, P/B, ROE, margen, deuda y dividend yield de empresas de TSX, NYSE y Nasdaq. Filtrá, ordená y comparalas lado a lado.',
            'features.f4.title': 'Dividendos, antes y después',
            'features.f4.desc': 'Calendario de ex-dates y pagos de lo que tenés, con los proventos ya recibidos confirmados uno por uno.',
            'features.f5.title': 'Hechos relevantes',
            'features.f5.desc': 'Filings de SEC EDGAR, resultados y noticias de tus empresas, en un inbox que se lee y se archiva.',
            'features.f6.title': 'Comunidad por ticker',
            'features.f6.desc_prefix': 'Tesis y preguntas de otros inversores. Una mención',
            'features.f6.desc_suffix': 'enlaza directo a la ficha de la empresa.',
            'acb.heading': 'Lo que tu broker no te dice cuando vendés',
            'acb.p1': 'Muchas jurisdicciones no aceptan FIFO: la ganancia de capital se calcula contra el costo promedio de todas tus compras de ese activo. Si comprás la misma acción en tres momentos y en dos cuentas distintas, ese promedio se mueve cada vez.',
            'acb.p2': 'TrueNorth lo recalcula solo, orden por orden, y guarda el número que vas a necesitar para tu declaración de impuestos.',
            'acb.li1': 'Compras, ventas, splits y órdenes en otra moneda convertidas al FX del día',
            'acb.li2': 'Un costo promedio por activo, aunque esté repartido en varias cuentas',
            'acb.li3': 'La ganancia realizada de cada venta, ya calculada',
            'acb.card_title': 'Historial de AAPL',
            'acb.card_units': '160 unidades',
            'acb.th_date': 'Fecha',
            'acb.th_operation': 'Operación',
            'acb.th_price': 'Precio',
            'acb.th_avg_cost': 'Costo prom.',
            'acb.op_buy': 'Compra',
            'acb.op_sell': 'Venta',
            'acb.realized_gain_label': 'Ganancia de capital realizada',
            'inbox.item1_source': 'SEC EDGAR · hace 2 h',
            'inbox.item1_text': 'Form 10-Q — Resultados del tercer trimestre',
            'inbox.item2_source': 'Dividendo · ex-date 15 nov',
            'inbox.item2_text': 'por acción — te tocan',
            'inbox.item3_source': 'Noticia · hace 6 h',
            'inbox.item3_text': 'Microsoft recorta su guidance de nube para el cuarto trimestre',
            'inbox.eyebrow': 'Seguimiento',
            'inbox.heading': 'Enterate por tu cartera, no por Twitter',
            'inbox.p1': 'TrueNorth mira solamente las empresas que tenés. Cada filing de SEC EDGAR, cada anuncio de dividendo y cada nota relevante llega a un inbox propio, con el ticker adelante y el monto que te toca ya calculado.',
            'inbox.p2': 'Sin feed infinito, sin notificaciones de empresas que no te importan.',
            'cta.heading': 'Empezá con una orden. El resto se arma solo.',
            'cta.p1': 'Creás la cuenta, importás tu historial o cargás la primera compra, y ya tenés portafolio, costo base y calendario de dividendos.',
            'cta.have_account': '¿Ya tenés cuenta?',
            'cta.login': 'Iniciá sesión',
            'footer.tagline': 'Herramienta de seguimiento y análisis para inversores. No es asesoramiento financiero ni fiscal: los cálculos son una ayuda, no un sustituto de tu contador.',
            'footer.col_product': 'Producto',
            'footer.link_portfolio': 'Portafolio',
            'footer.link_screener': 'Screener',
            'footer.link_dividends': 'Dividendos',
            'footer.col_account': 'Cuenta',
            'footer.link_signup': 'Crear cuenta',
            'footer.link_login': 'Iniciar sesión',
            'nav.login': 'Iniciar sesión',
            'nav.register': 'Crear cuenta'
        },
        en: {
            'hero.title': 'Your portfolio, with the analysis it’s missing.',
            'hero.subtitle': 'Bring all your investment accounts together in one portfolio. TrueNorth calculates the average cost base for every position, tracks your dividends, and gives you the fundamentals for every company you hold.',
            'hero.cta_register': 'Create a free account',
            'hero.cta_google': 'Continue with Google',
            'hero.trust1': 'Free, no card required',
            'hero.trust2': 'Multi-currency, with daily FX',
            'hero.trust3': 'Your data is yours alone',
            'card.total_equity': 'Total equity',
            'card.contributed': 'Contributed',
            'card.dividends_12m': 'Dividends 12m',
            'card.yield_on_cost': 'Yield on cost',
            'card.sector_plan': 'Plan by sector',
            'card.real_vs_target': 'actual vs. target',
            'card.sector_financial': 'Financials',
            'card.sector_energy': 'Energy',
            'card.sector_tech': 'Technology',
            'card.th_asset': 'Asset',
            'card.th_avg_cost': 'Avg. cost',
            'card.th_value': 'Value',
            'card.caption': 'Illustrative example of a dashboard, not real figures.',
            'brokers.import_from': 'Import your history from',
            'brokers.manual': '…or log each order by hand in 20 seconds',
            'features.heading': 'Six things you do today in five spreadsheets',
            'features.subheading': 'Each one lives here, with the same data and the same base currency.',
            'features.f1.title': 'Consolidated portfolio',
            'features.f1.desc': 'All your accounts in one portfolio, or filtered one at a time. Positions, cost, market value and P&L, always in your base currency.',
            'features.f2.title': 'Adjusted cost base (ACB)',
            'features.f2.desc': 'Weighted average cost recalculated on every purchase, so the capital gain on a sale is never a guess.',
            'features.f3.title': 'Fundamental screener',
            'features.f3.desc': 'P/E, P/B, ROE, margin, debt and dividend yield for TSX, NYSE and Nasdaq companies. Filter, sort and compare them side by side.',
            'features.f4.title': 'Dividends, before and after',
            'features.f4.desc': 'Ex-date and payment calendar for what you hold, with payouts already received confirmed one by one.',
            'features.f5.title': 'Material events',
            'features.f5.desc': 'SEC EDGAR filings, earnings and news for your companies, in an inbox you read and archive.',
            'features.f6.title': 'Community by ticker',
            'features.f6.desc_prefix': 'Theses and questions from other investors. A',
            'features.f6.desc_suffix': 'mention links straight to the company page.',
            'acb.heading': 'What your broker doesn’t tell you when you sell',
            'acb.p1': 'Many jurisdictions don’t accept FIFO: the capital gain is calculated against the average cost of all your purchases of that asset. If you buy the same stock at three different times and in two different accounts, that average shifts every time.',
            'acb.p2': 'TrueNorth recalculates it automatically, order by order, and keeps the number you’ll need for your tax return.',
            'acb.li1': 'Buys, sells, splits and orders in another currency converted at the day’s FX rate',
            'acb.li2': 'One average cost per asset, even if it’s spread across several accounts',
            'acb.li3': 'The realized gain on every sale, already calculated',
            'acb.card_title': 'AAPL history',
            'acb.card_units': '160 units',
            'acb.th_date': 'Date',
            'acb.th_operation': 'Transaction',
            'acb.th_price': 'Price',
            'acb.th_avg_cost': 'Avg. cost',
            'acb.op_buy': 'Buy',
            'acb.op_sell': 'Sell',
            'acb.realized_gain_label': 'Realized capital gain',
            'inbox.item1_source': 'SEC EDGAR · 2h ago',
            'inbox.item1_text': 'Form 10-Q — Third quarter results',
            'inbox.item2_source': 'Dividend · ex-date Nov 15',
            'inbox.item2_text': 'per share — you get',
            'inbox.item3_source': 'News · 6h ago',
            'inbox.item3_text': 'Microsoft cuts cloud guidance for the fourth quarter',
            'inbox.eyebrow': 'Tracking',
            'inbox.heading': 'Hear it from your portfolio, not from Twitter',
            'inbox.p1': 'TrueNorth only watches the companies you hold. Every SEC EDGAR filing, every dividend announcement and every relevant story lands in its own inbox, with the ticker up front and the amount you’re owed already calculated.',
            'inbox.p2': 'No infinite feed, no notifications from companies you don’t care about.',
            'cta.heading': 'Start with one order. The rest builds itself.',
            'cta.p1': 'Create your account, import your history or log your first purchase, and you already have a portfolio, cost base and dividend calendar.',
            'cta.have_account': 'Already have an account?',
            'cta.login': 'Log in',
            'footer.tagline': 'Tracking and analysis tool for investors. Not financial or tax advice: the calculations are a help, not a substitute for your accountant.',
            'footer.col_product': 'Product',
            'footer.link_portfolio': 'Portfolio',
            'footer.link_screener': 'Screener',
            'footer.link_dividends': 'Dividends',
            'footer.col_account': 'Account',
            'footer.link_signup': 'Create account',
            'footer.link_login': 'Log in',
            'nav.login': 'Log in',
            'nav.register': 'Sign up'
        },
        pt: {
            'hero.title': 'Sua carteira, com a análise que falta.',
            'hero.subtitle': 'Reúna todas as suas contas de investimento em uma única carteira. A TrueNorth calcula o custo médio de cada posição, acompanha seus dividendos e te dá os fundamentos de cada empresa que você tem.',
            'hero.cta_register': 'Criar conta grátis',
            'hero.cta_google': 'Continuar com o Google',
            'hero.trust1': 'Grátis, sem cartão',
            'hero.trust2': 'Multimoeda, com câmbio diário',
            'hero.trust3': 'Seus dados são só seus',
            'card.total_equity': 'Patrimônio total',
            'card.contributed': 'Aportado',
            'card.dividends_12m': 'Dividendos 12m',
            'card.yield_on_cost': 'Yield sobre custo',
            'card.sector_plan': 'Plano por setor',
            'card.real_vs_target': 'real vs. meta',
            'card.sector_financial': 'Financeiro',
            'card.sector_energy': 'Energia',
            'card.sector_tech': 'Tecnologia',
            'card.th_asset': 'Ativo',
            'card.th_avg_cost': 'Custo méd.',
            'card.th_value': 'Valor',
            'card.caption': 'Exemplo ilustrativo de um dashboard, não são valores reais.',
            'brokers.import_from': 'Importe seu histórico de',
            'brokers.manual': '…ou lance cada ordem manualmente em 20 segundos',
            'features.heading': 'Seis coisas que hoje você faz em cinco planilhas',
            'features.subheading': 'Cada uma vive aqui, com os mesmos dados e a mesma moeda base.',
            'features.f1.title': 'Carteira consolidada',
            'features.f1.desc': 'Todas as suas contas em uma única carteira, ou filtradas uma a uma. Posições, custo, valor de mercado e P&L, sempre na sua moeda base.',
            'features.f2.title': 'Custo base ajustado (ACB)',
            'features.f2.desc': 'Custo médio ponderado recalculado a cada compra, para que o ganho de capital de uma venda nunca seja uma estimativa.',
            'features.f3.title': 'Screener fundamentalista',
            'features.f3.desc': 'P/L, P/VP, ROE, margem, dívida e dividend yield de empresas da TSX, NYSE e Nasdaq. Filtre, ordene e compare lado a lado.',
            'features.f4.title': 'Dividendos, antes e depois',
            'features.f4.desc': 'Calendário de datas-ex e pagamentos do que você tem, com os proventos já recebidos confirmados um a um.',
            'features.f5.title': 'Fatos relevantes',
            'features.f5.desc': 'Filings da SEC EDGAR, resultados e notícias das suas empresas, em uma caixa de entrada que se lê e se arquiva.',
            'features.f6.title': 'Comunidade por ticker',
            'features.f6.desc_prefix': 'Teses e perguntas de outros investidores. Uma menção',
            'features.f6.desc_suffix': 'leva direto à página da empresa.',
            'acb.heading': 'O que sua corretora não te conta quando você vende',
            'acb.p1': 'Muitas jurisdições não aceitam FIFO: o ganho de capital é calculado sobre o custo médio de todas as suas compras daquele ativo. Se você compra a mesma ação em três momentos e em duas contas diferentes, essa média muda a cada vez.',
            'acb.p2': 'A TrueNorth recalcula tudo sozinha, ordem por ordem, e guarda o número que você vai precisar na sua declaração de imposto de renda.',
            'acb.li1': 'Compras, vendas, splits e ordens em outra moeda convertidas ao câmbio do dia',
            'acb.li2': 'Um custo médio por ativo, mesmo distribuído em várias contas',
            'acb.li3': 'O ganho realizado de cada venda, já calculado',
            'acb.card_title': 'Histórico da AAPL',
            'acb.card_units': '160 unidades',
            'acb.th_date': 'Data',
            'acb.th_operation': 'Operação',
            'acb.th_price': 'Preço',
            'acb.th_avg_cost': 'Custo méd.',
            'acb.op_buy': 'Compra',
            'acb.op_sell': 'Venda',
            'acb.realized_gain_label': 'Ganho de capital realizado',
            'inbox.item1_source': 'SEC EDGAR · há 2 h',
            'inbox.item1_text': 'Form 10-Q — Resultados do terceiro trimestre',
            'inbox.item2_source': 'Dividendo · data-ex 15 nov',
            'inbox.item2_text': 'por ação — você recebe',
            'inbox.item3_source': 'Notícia · há 6 h',
            'inbox.item3_text': 'Microsoft corta o guidance de nuvem para o quarto trimestre',
            'inbox.eyebrow': 'Acompanhamento',
            'inbox.heading': 'Fique sabendo pela sua carteira, não pelo Twitter',
            'inbox.p1': 'A TrueNorth olha apenas para as empresas que você tem. Cada filing da SEC EDGAR, cada anúncio de dividendo e cada notícia relevante chega numa caixa de entrada própria, com o ticker na frente e o valor que você recebe já calculado.',
            'inbox.p2': 'Sem feed infinito, sem notificações de empresas que não te interessam.',
            'cta.heading': 'Comece com uma ordem. O resto se monta sozinho.',
            'cta.p1': 'Você cria a conta, importa seu histórico ou lança a primeira compra, e já tem carteira, custo base e calendário de dividendos.',
            'cta.have_account': 'Já tem conta?',
            'cta.login': 'Entrar',
            'footer.tagline': 'Ferramenta de acompanhamento e análise para investidores. Não é consultoria financeira nem fiscal: os cálculos são uma ajuda, não um substituto do seu contador.',
            'footer.col_product': 'Produto',
            'footer.link_portfolio': 'Carteira',
            'footer.link_screener': 'Screener',
            'footer.link_dividends': 'Dividendos',
            'footer.col_account': 'Conta',
            'footer.link_signup': 'Criar conta',
            'footer.link_login': 'Entrar',
            'nav.login': 'Entrar',
            'nav.register': 'Criar conta'
        }
    };

    function detectDefaultLang() {
        var saved = null;
        try {
            saved = window.localStorage.getItem(STORAGE_KEY);
        } catch (err) {
            saved = null;
        }
        if (saved && SUPPORTED.indexOf(saved) !== -1) return saved;

        var browserLang = (navigator.language || 'es').slice(0, 2).toLowerCase();
        if (browserLang === 'en') return 'en';
        if (browserLang === 'pt') return 'pt';
        return 'es';
    }

    function applyLang(lang) {
        var dict = translations[lang] || translations.es;

        document.querySelectorAll('[data-i18n]').forEach(function (el) {
            var key = el.getAttribute('data-i18n');
            var value = dict[key];
            if (value !== undefined) el.textContent = value;
        });

        document.documentElement.setAttribute('lang', HTML_LANG[lang] || HTML_LANG.es);

        document.querySelectorAll('[data-lang-btn]').forEach(function (btn) {
            var isActive = btn.getAttribute('data-lang-btn') === lang;
            btn.classList.toggle('bg-ink', isActive);
            btn.classList.toggle('text-white', isActive);
            btn.classList.toggle('text-muted2', !isActive);
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });

        try {
            window.localStorage.setItem(STORAGE_KEY, lang);
        } catch (err) {
            // Private browsing or storage disabled — the switcher still
            // works for the current page, it just won't persist.
        }
    }

    var langButtons = document.querySelectorAll('[data-lang-btn]');
    langButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            applyLang(btn.getAttribute('data-lang-btn'));
        });
    });

    applyLang(detectDefaultLang());
})();
