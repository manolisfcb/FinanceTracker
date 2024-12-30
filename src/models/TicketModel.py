from app import db


class TicketModel(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    cvm_code = db.Column(db.String(10), nullable=True)      
    long_name = db.Column(db.String(100), nullable=True)
    short_name = db.Column(db.String(10), nullable=True)
    floatShares = db.Column(db.Integer, nullable=False)
    website = db.Column(db.String(100), nullable=True)
    sectorKey = db.Column(db.String(10), nullable=True)
    sector = db.Column(db.String(100), nullable=True)
    industry = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    
    
    
    def __init__(self, symbol, cvm_code, long_name, short_name, floatShares, website, sectorKey, sector, industry, country):
        self.symbol = symbol
        self.long_name = long_name
        self.cvm_code = cvm_code
        self.short_name = short_name
        self.floatShares = floatShares
        self.website = website
        self.sectorKey = sectorKey
        self.sector = sector
        self.industry = industry
        self.country = country
        
        
    def __repr__(self):
        return f'<TicketModel {self.symbol}>'
    
    def serialize(self):
        return {
            'id': self.id,
            'symbol': self.symbol,
            'long_name': self.long_name,
            'short_name': self.short_name,
            'floatShares': self.floatShares,
            'website': self.website,
            'sectorKey': self.sectorKey,
            'sector': self.sector,
            'industry': self.industry,
            'country': self.country
        }