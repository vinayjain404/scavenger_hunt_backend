/* Query for deleting a locations table */
drop table if exists locations;

/* Query for creating a locations table */
create table locations(
	id integer primary key autoincrement,
	user_id varchar,
	lat float,
	long float,
	address varchar,
	name varchar);

