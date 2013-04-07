# python imports
import os
import sqlite3
from flask import Flask, request, session, g, redirect, url_for, \
	abort, render_template, flash, json, jsonify

import settings

# configuration
DATABASE = settings.DB_NAME

app = Flask(__name__)
app.config.from_object(__name__)

DB_FILE_PATH = os.path.join(os.getcwd(), app.config['DATABASE'])
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
    cur = g.db.execute(query, args)
    rv = [dict((cur.description[idx][0], value)
               for idx, value in enumerate(row)) for row in cur.fetchall()]
    return (rv[0] if rv else None) if one else rv

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
    p1_id = request.form.get('source_id')
    p2_id = request.form.get('opponent_id')
    if not p1_id or not p2_id:
        data['status'] = FAIL
    else:
        data['status'] = SUCCESS
        g.db.execute('insert into game (p1_id, p2_id) \
            values (?, ?)', [p1_id, p2_id])
        g.db.commit()
        data['game_id'] = g.db.lastrowid
	return jsonify(data)

@app.route('/list_games/<player_id>/')
def list_games(player_id):
    """
    List games available for a player
    """
    games = query_db('select * from games where p1_id=? OR p2_id=?',
                [player_id, played_id])
    data = {}
    data['games'] = games
	return jsonify(data)

@app.route('/play_game/', methods = ['POST'])
def play_game():
    """
    Get the current state of the game for a given player and turn
    """
    game_id = request.form.get('game_id')
    player_id = request.form.get('player_id')

    game = query_db('select * from games where id=?',
                [game])
    data = {}
    if not game:
        data['status'] = FAIL
    else:
        data['status'] = SUCCESS
        
    data['game'] = game
	return jsonify(data)

@app.route('/play_turn/', methods = ['POST'])
def play_turn():
    """
    Play a turn for given user
    A turn comprises of submitting an image for matching to a given image by the
    opponent and sending an image for the next turn

    If the player is starting then he does not need to match an image instead
    he sends a image for the opponent to guess
    """
    game_id = request.form.get('game_id')
    label = request.form.get('label')
    player_id = request.form.get('player_id')
    match_image_url = request.form.get('match_image_url')
    upload_image_url = request.form.get('upload_image_url')
    move_result = 0 #default it to false

    if not match_image_url:
        move_type = 'U'
        # figure out if its first turn if no match image is passed
        add_image_to_training_set(upload_image_url)
        update_game_with_image_upload(upload_image_url, game_id, player_id)
    else:
        move_type = 'M'
        result = match_image_to_turn(match_image_url, game_id)
        remove_image_from_training_set(game_id)
        if not result:
            increment_player_missed_count(player_id)
        move_result = 1 if result else 0
        add_image_to_training_set(upload_image_url)
        update_game_with_image_upload(upload_image_url, game_id, player_id)

    create_move(game_id, player_id, move_type, upload_image_url, label, move_result)
    
def remove_image_from_training_set(game_id):
    """
    Remove the image from the training set via Iqengines API
    """
    pass

def update_game_with_image_upload(image_url, game_id, player_id, label):
    """
    Update the game db with image url, label and flip the active player turn
    """
	g.db.execute('update game set img_url = ?, label = ? where id = ?',
		[
            image_url,
            label,
            game_id
        ])
	g.db.commit()
    return g.db.lastrowid

def match_image_to_turn(image_url):
    """
    Match the image to the given image in the games last played image section
    returns True or False
    """
    return True

def add_image_to_training_set(image_url):
    """
    Add an image to the IQ engines training set
    """
    pass
 
def create_move(game_id, player_id, move_type, upload_image_url, label)
    """
    Add the current move to the move db
    """
    g.db.execute('insert into move (game_id, player_id, move_type, img_url, label) \
        values (?, ?, ?, ?, ?)', [game_id, played_id, move_type, upload_image_url, label])
    g.db.commit()
    print "Added a new move: %s" %g.db.lastrowid
    return g.db.lastrowid
    
if __name__ == '__main__':
	init_db()
	app.run(host='0.0.0.0', port=9000)
