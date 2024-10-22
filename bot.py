import time
from telegram.error import BadRequest
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from telegram.ext import MessageHandler, CallbackQueryHandler, filters
from sqlalchemy.orm import joinedload

from telegram_sales_bot.liqpay import LiqPayAPI, PUBLIC_KEY, PRIVAT_KEY
from telegram_sales_bot.models import Category, Product, Cart

TOKEN = '***************************************'
ITEMS_PER_PAGE = 5

class TelegramShopBot:
    def __init__(self, token, db_url):
        # Initialize bot and database connection
        self.application = ApplicationBuilder().token(token).build()
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.meta = MetaData()

        # Register bot commands
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("catalog", self.display_categories))
        self.application.add_handler(CommandHandler("cart", self.view_cart))


        self.application.add_handler(CallbackQueryHandler(self.remove_item, pattern='remove_'))
        self.application.add_handler(CallbackQueryHandler(self.change_quantity, pattern='change_'))
        self.application.add_handler(CallbackQueryHandler(self.display_categories, pattern='categories'))

        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_new_quantity))

        self.application.add_handler(CallbackQueryHandler(self.buy_cart, pattern='buy_cart'))
        self.application.add_handler(CallbackQueryHandler(self.buy_product, pattern='buy_'))
        self.application.add_handler(CallbackQueryHandler(self.display_items_with_pagination, pattern='category_'))

    # Command /start
    async def start(self, update: Update, context):
        await update.message.reply_text("Welcome to the shop! Use /catalog to view our products.")

    async def display_categories(self, update: Update, context):
        if update.callback_query:
            query = update.callback_query
            data = query.data.split('_')
            page = int(data[1]) if len(data) > 1 else 0
            message_func = query.edit_message_text
        else:

            query = update.message
            page = 0
            message_func = query.reply_text

        session = self.Session()

        categories = session.query(Category).all()

        paginated_categories, reply_markup = self.paginate_items_with_actions(
            items=categories,
            page=page,
            items_per_page=ITEMS_PER_PAGE,
            callback_data_prefix='categories',
            button_text_func=lambda category: category.name,
            button_callback_prefix='category_'
        )

        if not categories:
            await query.reply_text("No categories available.")
        else:
            category_list = [category.name for category in paginated_categories]
            category_message = "\n".join(category_list)

            await message_func(f"Categories (page {page + 1}):\n\n{category_message}", reply_markup=reply_markup)

        session.close()

    async def display_items_with_pagination(self, update: Update, context):
        query = update.callback_query
        data = query.data.split('_')
        category_id = int(data[1])
        page = int(data[2]) if len(data) > 2 else 0
        session = self.Session()

        products = session.query(Product).filter(Product.category_id == category_id).all()

        paginated_products, reply_markup = self.paginate_items_with_actions(
            items=products,
            page=page,
            items_per_page=ITEMS_PER_PAGE,
            callback_data_prefix=f'category_{category_id}',
            button_text_func=lambda product: f"Buy {product.name}",
            button_callback_prefix='buy_'
        )

        if not products:
            await query.edit_message_text("No products available in this category.")
        else:
            # Loop through paginated products and send product info with image
            for product in paginated_products:
                product_message = f"{product.name} - ₴{product.price}\n\n{product.description}"
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=product.image_url,  # URL to the product's image
                    caption=product_message,  # Product details as caption
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton(f"Buy {product.name}", callback_data=f'buy_{product.id}')]])
                )

            # Send pagination buttons (if available)
            if reply_markup:
                await context.bot.send_message(chat_id=query.message.chat_id, text="Navigate through pages:",
                                               reply_markup=reply_markup)

        session.close()
    def paginate_items_with_actions(self, items, page, items_per_page, callback_data_prefix, button_text_func,
                                    button_callback_prefix):
        """
        Universal pagination function that paginates items, adds action buttons, and creates navigation buttons.

        :param items: List of items to paginate
        :param page: Current page number (0-based)
        :param items_per_page: Number of items per page
        :param callback_data_prefix: Prefix for pagination callback_data (e.g., 'category_')
        :param button_text_func: Function that returns the button text for each item (e.g., 'Buy {item.name}')
        :param button_callback_prefix: Prefix for action buttons callback_data (e.g., 'buy_')
        :return: (paginated_items, InlineKeyboardMarkup)
        """
        start = page * items_per_page
        end = start + items_per_page
        paginated_items = items[start:end]

        keyboard = []
        for item in paginated_items:
            button_text = button_text_func(item)
            button_callback_data = f'{button_callback_prefix}{item.id}'
            keyboard.append([InlineKeyboardButton(button_text, callback_data=button_callback_data)])

        nav_buttons = []
        if start > 0:  # Show "Previous" if not on the first page
            nav_buttons.append(InlineKeyboardButton("Previous", callback_data=f'{callback_data_prefix}_{page - 1}'))
        if end < len(items):  # Show "Next" if there are more items
            nav_buttons.append(InlineKeyboardButton("Next", callback_data=f'{callback_data_prefix}_{page + 1}'))

        if nav_buttons:
            keyboard.append(nav_buttons)

        return paginated_items, InlineKeyboardMarkup(keyboard)

    async def buy_product(self, update: Update, context):
        query = update.callback_query
        product_id = int(query.data.split('_')[1])
        user_id = query.from_user.id
        session = self.Session()

        product = session.query(Product).filter(Product.id == product_id).first()

        if product:
            cart_item = session.query(Cart).filter(Cart.user_id == user_id, Cart.product_id == product_id).first()

            if cart_item:
                cart_item.quantity += 1
            else:
                cart_item = Cart(user_id=user_id, product_id=product_id, quantity=1)
                session.add(cart_item)

            session.commit()

            try:
                await query.edit_message_text(f"{product.name} has been added to your cart.")
            except BadRequest as e:
                await query.message.reply_text(f"{product.name} has been added to your cart.")
        else:
            await query.edit_message_text("This product is no longer available.")

        session.close()

    async def view_cart(self, update: Update, context):
        user_id = update.message.from_user.id
        session = self.Session()

        cart_items = session.query(Cart).join(Product).filter(Cart.user_id == user_id).all()

        if not cart_items:
            await update.message.reply_text("Your cart is empty.")
            session.close()
            return

        total_price = 0
        cart_list = []
        keyboard = []

        for cart_item in cart_items:
            cart_list.append(
                f"{cart_item.product.name} - {cart_item.quantity} pcs - ₴{cart_item.product.price * cart_item.quantity}")

            total_price += cart_item.product.price * cart_item.quantity

            keyboard.append([
                InlineKeyboardButton(f"Remove {cart_item.product.name}",callback_data=f'remove_{cart_item.product_id}'),
                InlineKeyboardButton(f"Change Quantity", callback_data=f'change_{cart_item.product_id}')
            ])

        cart_list = "\n".join(cart_list)
        cart_list += f"\n\nTotal: ₴{total_price:.2f}"

        keyboard.append([InlineKeyboardButton("Buy", callback_data='buy_cart')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(f"Your cart:\n\n{cart_list}", reply_markup=reply_markup)
        session.close()

    async def remove_item(self, update: Update, context):
        query = update.callback_query
        product_id = int(query.data.split('_')[1])
        user_id = query.from_user.id

        session = self.Session()

        # Remove the item from the cart
        session.query(Cart).filter(Cart.user_id == user_id, Cart.product_id == product_id).delete()
        session.commit()
        session.close()

        await query.answer("Item removed from the cart.")
        await query.message.reply_text("The item was removed from your cart.")

    async def change_quantity(self, update: Update, context):
        query = update.callback_query
        product_id = int(query.data.split('_')[1])
        session = self.Session()
        product = session.query(Product.name.label('name')).filter(Product.id == product_id).one()
        await query.message.reply_text(f"Please enter the new quantity for product {product.name}:")

        context.user_data['change_product_id'] = product_id

    async def set_new_quantity(self, update: Update, context):
        user_id = update.message.from_user.id
        try:
            new_quantity = int(update.message.text)
        except Exception:
            await update.message.reply_text(f" Please enter a valid **positive** number for the quantity. {update.message.text} is not number")
            return
        product_id = context.user_data.get('change_product_id')

        session = self.Session()

        cart_item = session.query(Cart).options(joinedload(Cart.product)).filter(Cart.user_id == user_id,
                                                                                 Cart.product_id == product_id).first()

        if cart_item:
            cart_item.quantity = new_quantity
            session.commit()

            await update.message.reply_text(
                f"Quantity for product '{cart_item.product.name}' updated to {new_quantity} pcs.")

        session.close()

    async def buy_cart(self, update: Update, context):
        query = update.callback_query
        user_id = query.from_user.id
        session = self.Session()

        cart_items = session.query(Cart).join(Product).filter(Cart.user_id == user_id).all()

        if not cart_items:
            await query.answer("Your cart is empty.")
            session.close()
            return

        total_price = float(sum(cart_item.product.price * cart_item.quantity for cart_item in cart_items))

        product_descriptions = ", ".join(
            [f"{cart_item.product.name} (x{cart_item.quantity})" for cart_item in cart_items])
        if len(product_descriptions) > 250:
            product_descriptions = product_descriptions[:247] + "..."

        order_id = f"order_{user_id}_{int(time.time())}"

        liqpay = LiqPayAPI(public_key=PUBLIC_KEY, private_key=PRIVAT_KEY)
        payment_url = liqpay.create_payment_url(amount=total_price,
                                                description=product_descriptions,
                                                order_id=order_id)

        keyboard = [[InlineKeyboardButton("Pay Now", url=payment_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(f"Click the button below to complete your purchase ₴{total_price} :", reply_markup=reply_markup)

        session.close()

    def run(self):
        self.application.run_polling()

bot = TelegramShopBot(TOKEN, 'postgresql://user:password@localhost:5432/your_db')
bot.run()
