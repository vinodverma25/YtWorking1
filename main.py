from app import app
from keep_alive import keep_alive_service

if __name__ == '__main__':
    # Start keep-alive service
    keep_alive_service.start()

    app.run(debug=False, host='0.0.0.0', port=5000)