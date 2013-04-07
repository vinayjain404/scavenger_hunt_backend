create table game(
	id integer primary key autoincrement,
	player1_id text,
	player2_id text,
	player_turn text
	img_url text,
	label text unique,
	player1_misses integer,
	player2_misses integer,
	winner text,
	FOREIGN KEY(player1_id) references players(fb_id),
	FOREIGN KEY(player2_id) references players(fb_id),
	FOREIGN KEY(winner) references players(fb_id),
	FOREIGN KEY(player_turn) references players(fb_id)
);


create table moves(
  	id integer primary key autoincrement,
  	game_id integer, 
        player_id text,
  	move_type text default 'U',
	img_url text,
	label text unique,
	result text,
	FOREIGN KEY(game_id) references game(id),
	FOREIGN KEY(player_id) references players(fb_id)
);
	

create table players(
	fb_id text primary key,
	games_played integer  default 0,
	games_won integer default 0
);
