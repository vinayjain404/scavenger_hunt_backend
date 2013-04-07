# python imports
from datetime import datetime
import os
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
	abort, render_template, flash, json, jsonify

from pyiqe import Api
import settings
import time
import urllib
import urllib2
import utils

# configuration
DATABASE = settings.DB_NAME

app = Flask(__name__)
app.config.from_object(__name__)

DB_FILE_PATH = os.path.join(os.getcwd(), app.config['DATABASE'])
DEBUG = True
FAIL = 'fail'
SUCCESS = 'ok'

def connect_db():
	return sqlite3.connect(DB_FILE_PATH)

def init_db():
	# creates the schema in the db if not present
	if not os.path.exists(DB_FILE_PATH):
		cur = connect_db()
		query_file = open(os.path.join(os.getcwd(), 'initialize_db.sql'))
		cur.executescript(query_file.read())

def query_db(query, args=(), one=False):
    print "Executing query: %s, args: %s" %(query, args)
    cur = g.db.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
               for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv

def replace(table, fields, values):
    # g.db is the database connection
    cur = g.db.cursor()
    query = 'REPLACE INTO %s (%s) VALUES (%s)' % (
        table,
        ', '.join(fields),
        ', '.join(['?'] * len(values))
    )
    print "Executing query: %s, values: %s" %(query, values)
    cur.execute(query, values)
    g.db.commit()

    cur.close()

def update(table, fields, values, id):
    # g.db is the database connection
    cur = g.db.cursor()
    clause = ' = ?, '.join(fields)
    clause = "%s = ?" %clause
    query = 'UPDATE %s set %s WHERE id=?' % (
        table,
        clause
    )
    print "Executing query: %s, values: %s and id: %s" %(query, values, id)
    values.append(id)
    cur.execute(query, values)
    g.db.commit()

    cur.close()

def insert(table, fields, values):
    # g.db is the database connection
    cur = g.db.cursor()
    query = 'INSERT INTO %s (%s) VALUES (%s)' % (
        table,
        ', '.join(fields),
        ', '.join(['?'] * len(values))
    )
    print "Executing query: %s, values: %s" %(query, values)
    cur.execute(query, values)
    g.db.commit()

    id = cur.lastrowid
    cur.close()
    return id

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    g.db.close()

@app.route('/create_game/', methods = ['POST'])
def create_game():
    """
    API endpoint to create a new game.
    """
    data = {}
    p1_id = request.form.get('player1_id')
    p2_id = request.form.get('player2_id')

    if not p1_id or not p2_id:
        data['status'] = FAIL
    else:
        replace('player', ['fb_id'], [p1_id])
        replace('player', ['fb_id'], [p2_id])

        data['status'] = SUCCESS
        cur_time = int(time.time())
        fields = ['player1_id', 'player2_id', 'last_updated', 'player_turn']
        values = [p1_id, p2_id, cur_time, p1_id]
        id = insert('game', fields, values)
        data['game_id'] = id
    return jsonify(data=data)

@app.route('/list_games/<player_id>/')
def list_games(player_id):
    """
    List games available for a player
    """
    games = query_db('select * from game where player1_id=? OR player2_id=? and (img_url not NULL OR img_url != (null)',
                [player_id, player_id])
    data = {}

    data['games'] = games
    data['timestamp'] = int(time.time())
    return jsonify(data)

@app.route('/updated_games/<player_id>/<timestamp>')
def updated_games(player_id, timestamp):
    """
    List games available for a player
    """
    games = query_db('select * from game where last_updated > ? AND img_url NOT NULL AND (player1_id=? OR player2_id=?)',
                [int(timestamp), player_id, player_id])
    data = {}

    data['games'] = games
    data['timestamp'] = int(time.time())
    return jsonify(data)

@app.route('/upload_turn/', methods = ['POST'])
def upload_turn():
    """
    Play a upload turn for the user
    """
    print "Json response: %s" %request.data
    data = json.loads(request.data)
    game_id = data['game_id']
    player_id = data['player_id']
    upload_image = data['upload_image']
    move_result = 0 # default it to false
    label = utils.create_unique_label()

    upload_image_url = get_image_url_from_imgur(upload_image)
    print "Image from imgur upload: %s" %upload_image_url
    player_number = which_player(game_id, player_id) # detect player 1 or 2

    move_type = 'U'

    iq_image_id = add_image_to_training_set(upload_image, label)
    update_game_with_image_upload(upload_image_url, game_id, player_id, label, iq_image_id)
    create_move(game_id, player_id, move_type, upload_image_url, label, move_result)

    # Swap the turn for the given player
    swap_turn(game_id, player_number)

    # Save match as the next turn type
    save_turn(game_id, 'M')

    return jsonify({"status": SUCCESS})

@app.route('/match_turn/', methods = ['POST'])
def match_turn():
    """
    Play a match turn for a given user
    """
    print "JSON response: %s" %request.data
    data = json.loads(request.data)
    game_id = data['game_id']
    player_id = data['player_id']
    match_image = data['match_image'] # base 64 encoded data for the image
    move_result = 0 # default it to false
    label = utils.create_unique_label()

    match_image_url = get_image_url_from_imgur(match_image)
    print "Imgur upload link: %s" %match_image_url
    player_number = which_player(game_id, player_id) # detect player 1 or 2

    move_type = 'M'
    result = match_image_to_turn(match_image, game_id)
    remove_image_from_training_set(game_id)

    if not result:
        count = increment_player_missed_count(game_id, player_number)

        if count == settings.MAX_MISSES:
            update_results(game_id, player_number)

    move_result = 1 if result else 0
          
    create_move(game_id, player_id, move_type, match_image_url, label, move_result)

    # Save next turn type as upload
    save_turn(game_id, 'U')

    status = SUCCESS if result else FAIL
    return jsonify({"status": status})

def save_turn(game_id, move_type):
    """
    Saves the current turn type for a given game id and turn type
    """
    cur_time = int(time.time())
    fields = ['turn_type', 'last_updated']
    values = [move_type, cur_time]
    update('game', fields, values, game_id)
    
def which_player(game_id, player_id):
    """
    Returns if player 1 or 2 is the player for the given game
    """
    game = query_db('select * from game where id=?', [game_id], one=True)

    if game['player1_id'] == player_id:
        return 1
    elif game['player2_id'] == player_id:
        return 2
    else:
        print "Player: %s is not a valid player for game: %s" %(player_id, game_id)
        return None

def update_results(game_id, loser_number):
    """
    Update the winner of the game
    The winner is decided when one of the player gets MAX_MISSES and he loses.
    """
    if loser_number == 1:
        winner_player = 2
    else:
        winner_player = 1

    game = query_db('select * from game where id=?', [game_id], one=True)
    loser_player_id = 'player%d_id' %loser_number
    winner_player_id = 'player%d_id' %winner_player
    
    # update winner in the game db
    cur_time = int(time.time())
    fields = ['winner', 'last_updated']
    values = [game[winner_player_id], cur_time]
    update('game', fields, values, game_id)

    # update winner and loser in the players table
    player = query_db('select * from player where fb_id=?', [winner_player_id], one=True)
    current_games_played = player['games_played']
    current_games_won = player['games_won']
    fields = ['games_played', 'games_won']
    values = [current_games_played+1, current_games_won+1]
    update('player', fields, values, winner_player_id)

    # update loser in the players table
    player = query_db('select * from player where fb_id=?', [loser_player_id], one=True)
    current_games_played = player['games_played']
    fields = ['games_played']
    values = [current_games_played+1]
    update('player', fields, values, loser_player_id)

def increment_player_missed_count(game_id, player_number):
    """
    Increment player missed count
    """
    game = query_db('select * from game where id=?', [game_id], one=True)
    player_missed_count_field = 'player%d_misses' %player_number
    new_player_count = game[player_missed_count_field] + 1

    cur_time = int(time.time())
    fields = [player_missed_count_field, 'last_updated']
    values = [new_player_count, cur_time]
    update('game', fields, values, game_id)

    return new_player_count

def get_image_url_from_imgur(base64_image):
    """
    Upload a base64 image to imgur and return a link
    """
    headers = {'authorization': 'Client-ID %s' %settings.IMGUR_CLIENT_ID}
    params = {}
    params['image'] = base64_image
    params_encoded = urllib.urlencode(params)
    url = settings.IMGUR_URL
    print "url: %s" %url
    print "params: %s" %params
    print "headers: %s" %headers
    try:
        request_object = urllib2.Request(url, params_encoded, headers)
        response = urllib2.urlopen(request_object)
        resp = response.read()
        data = json.loads(resp)

        if data['status'] != 200:
            return None
        else:
            return data['data']['link']
    except Exception as ex:
        print "Exception raised for get image urls from imgur %s" %str(ex)
        return None

def swap_turn(game_id, player_number):
    """
    Swap the player turn for the given game
    """
    game = query_db('select * from game where id=?', [game_id], one=True)

    if player_number == 1:
        next_turn_player_number = 2
    else:
        next_turn_player_number = 1
        
    next_turn_player_id = 'player%d_id' %next_turn_player_number 

    cur_time = int(time.time())
    fields = ['player_turn', 'last_updated']
    values = [next_turn_player_id, cur_time]
    update('game', fields, values, game_id)
    
def match_image_to_turn(image, game_id):
    """
    Match the image to the given image in the games last played image section
    returns True or False
    """
    api = Api(settings.IQE_KEY, settings.IQE_SECRET)

    label = utils.create_unique_label()
    filename = "/tmp/%s" %label
    file = open(filename, "w")

    file.write(image.decode('base64'))
    file.close()

    response, qid = api.query(filename, device_id=label)
    print "Object created with response: %s and qid: %s" %(response, qid)

    game = query_db('select * from game where id=?', [game_id], one=True)
    expected_label = game['label']

    try:
        # update method
        result = api.update(device_id=label)

        data = result['data']
        if "results" in data:
            print data['results']
            if isinstance(data['results'], list):
                actual_labels = [result['qid_data']['labels'] for result in data['results']]
                result = expected_label in actual_labels
            else:
                actual_labels = data['results']['qid_data']['labels']
                result = expected_label == actual_labels
            print "Actual labels: %s" %actual_labels
            print "Expected labels: %s" %expected_label
            print "Result for the image match is: %s" %result
            if result:
                return result
    except Exception as ex:
        print "Match raised ane exception"
        import traceback
        traceback.print_exc()

    # result method
    response = api.result(qid)
    data = response['data']

    print "Data response: %s" %response

    if "results" in data:
        if isinstance(data['results'], list):
            actual_labels = [result['labels'] for result in data['results']]
            result = expected_label in actual_labels
        else:
            actual_labels = data['results']['labels']
            result = expected_label == actual_labels
        print "Actual labels: %s" %actual_labels
        print "Expected labels: %s" %expected_label
        print "Result for the image match is: %s" %result
        return result
    else:
        return False



def add_image_to_training_set(image, label):
    """
    Add an image to the IQ engines training set
    """
    api = Api(settings.IQE_KEY, settings.IQE_SECRET)
    
    filename = "/tmp/%s" %label
    file = open(filename, "w")

    file.write(image.decode('base64'))
    file.close()

    response = api.objects.create(name=label, images=[filename])
    print "Add image to training set response: %s" %response
    obj_id = response['obj_id']
    return obj_id 

def remove_image_from_training_set(game_id):
    """
    Remove the image from the training set via Iqengines API
    """
    api = Api(settings.IQE_KEY, settings.IQE_SECRET)

    game = query_db('select * from game where id=?',
                [game_id], one=True)
    id = game['iq_image_id']
    response = api.objects.delete(id)
    print "Deleting training set image with id: %s and response: %s" %(id, response)

def update_game_with_image_upload(image_url, game_id, player_id, label, iq_image_id):
    """
    Update the game db with image url, label and flip the active player turn
    """
    cur_time = int(time.time())
    fields = ['img_url', 'label', 'last_updated', 'iq_image_id']
    values = [image_url, label, cur_time, iq_image_id]
    update('game', fields, values, game_id)

def create_move(game_id, player_id, move_type, upload_image_url, label, move_result):
    """
    Add the current move to the move db
    """
    cur_time = int(time.time())
    fields = ['game_id', 'player_id', 'move_type', 'img_url', 'label', 'result', 'time_updated']
    values = [game_id, player_id, move_type, upload_image_url, label, move_result, cur_time]
    id = insert('move', fields, values)
    print "Added a new move: %s" %id
    return id

if __name__ == '__main__':
	init_db()
	app.run(debug=DEBUG, host='0.0.0.0', port=9000)
