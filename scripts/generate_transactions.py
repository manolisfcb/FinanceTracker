import random
from faker import Faker
from app import app, db
from src.models import UserModel, TransactionModel, Category

fake = Faker()

def generate_transactions():
    with app.app_context():  # Ensure the app context is active

        # Create categories
        categories = [
            "Bills",
            "Food",
            "Clothes",
            "Medical",
            "Housing",
            "Salary",
            "Social",
            "Transport",
            "Vacation",
        ]

        for category_name in categories:
            existing_category = Category.query.filter_by(name=category_name).first()
            if not existing_category:
                category = Category(name=category_name, type=random.choice(['INCOME', 'EXPENSE']))
                db.session.add(category)
        db.session.commit()

        # Get or create the user
        user = UserModel.query.filter_by(username='bugbytes').first()
        if not user:
            user = UserModel(username='bugbytes', password='hashed_test_password', email='bug@gmail.com')
            db.session.add(user)
            db.session.commit()

        # Create random transactions
        all_categories = Category.query.all()
        for _ in range(20):
            transaction = TransactionModel(
                category=random.choice(all_categories),
                user_id=user.id,
                amount=random.uniform(1, 2500),
                date=fake.date_between(start_date='-1y', end_date='today'),
                type=random.choice(['INCOME', 'EXPENSE']),
                description=fake.sentence(),
            )
            db.session.add(transaction)
        db.session.commit()

        print("Test data generated successfully!")

generate_transactions()