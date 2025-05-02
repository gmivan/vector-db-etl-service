// https://pm2.keymetrics.io/docs/usage/application-declaration/
module.exports = {
  apps: [
    {
      name: "db_service_server",
      script: "db_service_server.py",
      args: "-c gunicorn_conf.py",
      interpreter: "../venv/bin/python3",
      instances: 1,  // Spawn this many instances
      autorestart: false,  // Automatically restart if the app crashes
      max_memory_restart: "1G",  // Restart if memory usage exceeds 1GB
      // time: true,  // Log timestamps
      log_date_format: "HH:mm:ss.SSS",  // Log timestamps with this format
    },
  ],
};
