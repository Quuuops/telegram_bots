from sqlalchemy import Column, Integer, String, DECIMAL, Text, ForeignKey, BigInteger, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Category(Base):
    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)

    products = relationship('Product', back_populates='category')

class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(DECIMAL(10, 2), nullable=False)
    image_url = Column(String(255))

    category = relationship('Category', back_populates='products')
    order_items = relationship('OrderItem', back_populates='product')
    cart_items = relationship('Cart', back_populates='product')

class Cart(Base):
    __tablename__ = 'carts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False)

    product = relationship('Product', back_populates='cart_items')

class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    total_amount = Column(DECIMAL(10, 2))
    order_date = Column(TIMESTAMP, server_default=func.now())  # Defaults to the current timestamp
    status = Column(String(50), nullable=False)

    order_items = relationship('OrderItem', back_populates='order')

class OrderItem(Base):
    __tablename__ = 'order_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)

    order = relationship('Order', back_populates='order_items')
    product = relationship('Product', back_populates='order_items')
