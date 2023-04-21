# rht-tms


sudo apt-get update
sudo apt-get install apache2 software-properties-common mysql-server
sudo add-apt-repository ppa:ondrej/php
sudo apt-get install -y php
pip install Flask Flask-SQLAlchemy Flask-Login python-barcode openpyxl Flask-Mail  Flask-Migrate
sudo mysql_secure_installation

CREATE DATABASE rht_tms;

USE rht_tms;

CREATE TABLE students (

cli_ID INT AUTO_INCREMENT PRIMARY KEY,
student_ID VARCHAR(255) NOT NULL UNIQUE,
student_NAME VARCHAR(255) NOT NULL,
student_SNAME VARCHAR(255) NOT NULL,
student_GSM VARCHAR(255),
student_EMAIL VARCHAR(255) NOT NULL UNIQUE,
student_DEP VARCHAR(255) NOT NULL

);

CREATE TABLE event ( 

event_ID char(10)  PRIMARY KEY, 
event_name VARCHAR(255) NOT NULL, 
event_date DATE NOT NULL
);

CREATE TABLE `user` (

  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` varchar(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)

) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `user` (`username`, `email`, `password`, `role`) VALUES ('admin', 'basarorsel@std.iyte.edu.tr', '93745696049ce21ca9c06f20bdce44719440fe4f8c409c473a171bb4d62e53df', 'super_user'
);

