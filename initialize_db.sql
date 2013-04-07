


create table game(
	id integer primary key,
	player1_id text,
	player2_id text,
	img_url text,
	label text unique key,
	player1_misses integer,
	player2_misses integer,
	winner text,
	FOREIGN KEY(player1_id) references players(fb_id),
	FOREIGN KEY(player2_id) references players(fb_id),
	FOREIGN KEY(winner) references players(fb_id)
);


create table moves(
  	id integer primary key
  	game_id integer 
        player_id text
  	type text default 'upload'
	img_url text
	label text unique key
	result text default 'N'
	FOREIGN KEY(game_id) references game(id)
	FOREIGN KEY(player_id) references players(id)
);
	

create table players(
	fb_id text
	games_played integer  default 0
	games_won integer default 0
);

