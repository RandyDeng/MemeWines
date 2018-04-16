#!flask/bin/python
import datetime

from flask import Flask
from flask import flash, redirect, render_template, request
from flask_wtf import CsrfProtect, FlaskForm

from google.appengine.ext import ndb
from google.appengine.api import users

from wtforms import (FieldList, FormField,
                     HiddenField, StringField, SubmitField)
from wtforms.validators import DataRequired, Length, Regexp

DEFAULT_WINE = "doge"
MAX_WINE_LIST_SIZE = 255


class AddWine(FlaskForm):
    wine_type = StringField("Wine Type:", validators=[
                            DataRequired(),
                            Length(min=1, max=30),
                            Regexp('^[a-zA-Z0-9_-]*$')])
    country = StringField('Country of Origin:', validators=[
                            DataRequired(),
                            Length(min=1, max=30),
                            Regexp('^[a-zA-Z0-9_-]*$')])
    region = StringField('Region:', validators=[
                            DataRequired(),
                            Length(min=1, max=30),
                            Regexp('^[a-zA-Z0-9_-]*$')])
    variety = StringField('Variety:', validators=[
                            DataRequired(),
                            Length(min=1, max=30),
                            Regexp('^[a-zA-Z0-9_-]*$')])
    winery_name = StringField('Winery Name:', validators=[
                            DataRequired(),
                            Length(min=1, max=30),
                            Regexp('^[a-zA-Z0-9_-]*$')])
    year = StringField('Year:', validators=[
                            DataRequired(),
                            Length(min=1, max=4),
                            Regexp('^[0-9]*$')])
    price = StringField('Price:', validators=[
                            DataRequired(),
                            Length(min=1),
                            Regexp('^[0-9.]*$')])
    submit = SubmitField("Add Wine")


class SearchWine(FlaskForm):
    wine_type = StringField('Wine Type:', validators=[
                            Regexp('^[a-zA-Z0-9_-]*$')])
    country = StringField('Country of Origin:', validators=[
                            Regexp('^[a-zA-Z0-9_-]*$')])
    region = StringField('Region:', validators=[
                            Regexp('^[a-zA-Z0-9_-]*$')])
    variety = StringField('Variety:', validators=[
                            Regexp('^[a-zA-Z0-9_-]*$')])
    winery_name = StringField('Winery Name:', validators=[
                            Regexp('^[a-zA-Z0-9_-]*$')])
    submit = SubmitField("Begin Search")


class UpdateQuantity(FlaskForm):
    amount = StringField('Qty', validators=[
                            DataRequired(),
                            Regexp('^[0-9]*$')])
    item_key = HiddenField('Item Key', validators=[DataRequired()])


class UpdateCart(FlaskForm):
    quantities = FieldList(FormField(UpdateQuantity), min_entries=1)
    update = SubmitField("Update Quantity")


class Wine(ndb.Model):
    wine_type = ndb.StringProperty()
    country = ndb.StringProperty()
    region = ndb.StringProperty()
    variety = ndb.StringProperty()
    winery_name = ndb.StringProperty()
    year = ndb.IntegerProperty()
    price = ndb.FloatProperty()


class UserCart(ndb.Model):
    wine_item = ndb.StringProperty()
    amount = ndb.IntegerProperty()
    purchased = ndb.BooleanProperty()


class UserHistory(ndb.Model):
    cart = ndb.StringProperty(repeated=True)
    timestamp = ndb.StringProperty()
    total = ndb.FloatProperty()
    user = ndb.StringProperty()


def get_wine_key(wine_type=DEFAULT_WINE):
    return ndb.Key("Wine", wine_type)


def get_user_key(nickname):
    return ndb.Key("UserCart", nickname)


def get_user_history_key(nickname):
    return ndb.Key("UserHistory", nickname)


def retrieve_wines(wine_type):
    if wine_type is None:
        data = Wine.query()
    else:
        data = Wine.query(ancestor=get_wine_key(wine_type))
    wines = data.fetch(MAX_WINE_LIST_SIZE)
    return wines


def retrieve_user_cart(nickname):
    if nickname is None:
        return []
    else:
        data = UserCart.query(ancestor=get_user_key(nickname))
        cart_data = data.fetch(MAX_WINE_LIST_SIZE)
        cart = []
        for item in cart_data:
            if item.purchased is False:
                cart.append(item)
    return cart


def retrieve_user_history(nickname):
    if nickname is None:
        return []
    else:
        data = UserHistory.query(ancestor=get_user_history_key(nickname))
    history = data.fetch(MAX_WINE_LIST_SIZE)
    return history


def history_to_json(history):
    history_json = []
    for purchase in history:
        cart = []
        for cart_key in purchase.cart:
            cart.append(ndb.Key(urlsafe=cart_key).get())

        history_json.append(
            {
                'timestamp': purchase.timestamp,
                'total': '%.2f' % purchase.total,
                'user': purchase.user,
                'cart': cart_to_json(cart)
            }
        )
    history_json = sorted(history_json, reverse=True, key=lambda x:
                          datetime.datetime.strptime(x['timestamp'],
                                                     '%Y-%m-%d %H:%M:%S'))
    return history_json


def cart_to_json(cart):
    shopping_cart = []
    for item in cart:
        wine = ndb.Key(urlsafe=item.wine_item).get()
        item_json = wine_to_json(wine)
        item_json['amount'] = item.amount
        item_json['key'] = item.key.urlsafe()
        shopping_cart.append(item_json)
    return shopping_cart


def wine_to_json(wine):
    return {
        'wine_type': wine.wine_type,
        'country': wine.country,
        'region': wine.region,
        'variety': wine.variety,
        'winery_name': wine.winery_name,
        'year': wine.year,
        'price': '%.2f' % wine.price,
        'key': wine.key.urlsafe()
    }


def is_duplicate_wine(wine_key):
    name = users.get_current_user().nickname()
    cart = retrieve_user_cart(name)
    for item in cart:
        if item.wine_item.encode('utf-8') == wine_key:
            return True
    return False


def compute_total_price(cart_list):
    total = 0
    for item in cart_list:
        total = total + (ndb.Key(urlsafe=item.wine_item).get().price *
                         item.amount)
    return total


def is_logged_in():
    user = users.get_current_user()
    if user:
        return True
    return False


app = Flask(__name__, static_url_path="")
CsrfProtect(app)
app.config['CSRF_ENABLED'] = True
app.secret_key = 'A0Zrdf;e3yX R~XHH!jmsFGR@$()T'


@app.route('/', methods=['GET'])
def home():
    user = users.get_current_user()
    if user:
        nickname = user.nickname()
        logout_url = users.create_logout_url('/')
        greeting = ('Welcome, <strong>{}</strong>! '
                    '(<a href="{}">Sign Out</a>)').format(
                    nickname, logout_url)
    else:
        login_url = users.create_login_url('/')
        greeting = '<a href="{}">Sign in</a>'.format(login_url)

    return render_template('index.html', login=greeting)


@app.route('/browse/<string:wine_type>', methods=['GET'])
def browse(wine_type):
    wine_list = []
    wines = retrieve_wines(wine_type)
    for wine in wines:
        wine_list.append(wine_to_json(wine))
    return render_template('browse.html', wine_list=wine_list)


@app.route('/search', methods=['GET', 'POST'])
def search():
    form = SearchWine()
    new_list = []
    if request.method == 'POST':
        if (not form.wine_type.data and
            not form.country.data and
            not form.region.data and
            not form.variety.data and
                not form.winery_name.data):
            flash("Please enter at least 1 input")
            return render_template('search.html',
                                   form=form, wine_list=new_list)
        if form.validate_on_submit():
            wine_list = retrieve_wines(None)
            for wine in wine_list:
                if (form.wine_type.data.encode('utf-8').lower()
                        in wine.wine_type.encode('utf-8').lower() and
                    form.country.data.encode('utf-8').lower()
                        in wine.country.encode('utf-8').lower() and
                    form.region.data.encode('utf-8').lower()
                        in wine.region.encode('utf-8').lower() and
                    form.variety.data.encode('utf-8').lower()
                        in wine.variety.encode('utf-8').lower() and
                    form.winery_name.data.encode('utf-8').lower()
                        in wine.winery_name.encode('utf-8').lower()):
                    new_list.append(wine_to_json(wine))
            if not new_list:
                flash("No data was found for your search")
            return render_template('search.html',
                                   form=form, wine_list=new_list)
        else:
            flash("""Please enter valid inputs:
                all inputs must be alphanumeric""")
            return render_template('search.html',
                                   form=form, wine_list=new_list)
    return render_template('search.html', form=form, wine_list=new_list)


@app.route('/add_wine', methods=['GET', 'POST'])
def add_wine():
    form = AddWine()
    if request.method == 'POST':
        if form.validate_on_submit():
            new_wine = Wine(parent=get_wine_key(form.wine_type.data),
                            wine_type=form.wine_type.data,
                            country=form.country.data,
                            region=form.region.data,
                            variety=form.variety.data,
                            winery_name=form.winery_name.data,
                            year=int(form.year.data),
                            price=float(int(float(form.price.data)*100)/100.))
            new_wine.put()
            flash("Wine has been added successfully!")
            return redirect('/add_wine')
        else:
            flash("""Please enter valid inputs:
                All inputs must be alphanumeric,
                except for year and price, which should be a valid number""")
            return render_template('add_wine.html', form=form)
    return render_template('add_wine.html', form=form)


@app.route('/cart', methods=['GET', 'POST'])
def cart():
    if not is_logged_in():
        flash("Please login before buying anything")
        return redirect('/')

    name = users.get_current_user().nickname()
    cart = retrieve_user_cart(name)
    form_data = []
    for item in cart:
        form_data.append(
            {
                'amount': 1,
                'item_key': item.key.urlsafe()
            }
        )
    form = UpdateCart(quantities=form_data)
    if request.method == 'POST':
        if form.validate_on_submit():
            for item in form.quantities.data:
                if int(item['amount']) is 0:
                    ndb.Key(urlsafe=item['item_key']).delete()
                else:
                    user_cart = ndb.Key(urlsafe=item['item_key']).get()
                    user_cart.amount = int(item['amount'])
                    user_cart.put()
            flash("Your cart has been successfully updated")
        else:
            flash("Please enter a valid quantity")
    cart = retrieve_user_cart(name)
    cart_json = cart_to_json(cart)
    return render_template('cart.html', shopping_cart=cart_json,
                           form=form, total='%.2f' % compute_total_price(cart))


@app.route('/add_to_cart/<string:wine_key>', methods=['GET'])
def add_to_cart(wine_key):
    if not is_logged_in():
        flash("Please login before buying anything")
        return redirect('/')

    if is_duplicate_wine(wine_key):
        flash("You have already added this wine to your cart")
        return redirect('/cart')

    name = users.get_current_user().nickname()
    new_item = UserCart(parent=get_user_key(name),
                        wine_item=wine_key,
                        amount=1,
                        purchased=False)
    new_item.put()
    flash("Your item has been added to your cart successfully!")
    return redirect('/cart')


@app.route('/delete_item/<string:item_key>', methods=['GET'])
def delete_item(item_key):
    if not is_logged_in():
        flash("Please login before modifying your cart")
        return redirect('/')

    ndb.Key(urlsafe=item_key).delete()
    flash("Item has been successfully deleted from cart")
    return redirect('/cart')


@app.route('/purchase', methods=['POST'])
def purchase():
    if not is_logged_in():
        flash("Please login before purchasing anything")
        return redirect('/')

    name = users.get_current_user().nickname()
    cart_keys = []
    cart = retrieve_user_cart(name)

    if not cart:
        flash("Please add items to your cart before purchasing")
        return redirect('/cart')

    for item in cart:
        cart_keys.append(item.key.urlsafe())
        item.purchased = True
        item.put()
    time = datetime.datetime.now().replace(
        microsecond=0).isoformat(' ')
    new_history = UserHistory(parent=get_user_history_key(name),
                              cart=cart_keys,
                              timestamp=time,
                              total=compute_total_price(cart),
                              user=name)
    new_history.put()
    flash("Thank you for your purchase! "
          "Your wines will be delivered shortly.")
    return redirect('/cart')


@app.route('/history', methods=['GET'])
def history():
    if not is_logged_in():
        flash("Please login to see your history")
        return redirect('/')

    name = users.get_current_user().nickname()
    history_list = retrieve_user_history(name)
    history = history_to_json(history_list)
    return render_template('history.html', history=history)


# Run Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
