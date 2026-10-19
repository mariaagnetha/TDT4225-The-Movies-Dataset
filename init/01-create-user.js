const dbName = process.env.MONGO_INITDB_DATABASE || 'mydatabase';
const user = process.env.MONGO_INITDB_USERNAME || 'myuser';
const pwd = process.env.MONGO_INITDB_PASSWORD || 'mypassword';

db = db.getSiblingDB(dbName);
db.createUser({
  user: user,
  pwd: pwd,
  roles: [
    { role: 'readWrite', db: dbName },
    { role: 'read', db: 'test'}
  ]
});