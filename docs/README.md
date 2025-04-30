# Voting System

A secure and efficient web-based voting system that uses QR codes for authentication.

## Features

- Secure token-based voting system
- QR code generation for voting tokens
- Real-time voting statistics
- Admin dashboard for token management
- Responsive web interface
- Docker containerization support
- Fly.io deployment ready

## System Requirements

- Python 3.9 or higher
- SQLite3
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd vote_system
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Initialize the database:
```bash
python scripts/init_db.py
```

4. Run the application:
```bash
python app.py
```

## Usage

### Admin Interface
- Access the admin dashboard at `/admin`
- Generate voting tokens
- Monitor voting statistics
- View vote distribution

### Voting Process
1. Admin generates voting tokens
2. Tokens are distributed to voters
3. Voters scan QR code or enter token
4. Voters cast their votes
5. Results are updated in real-time

### Deployment

#### Local Deployment
1. Follow installation steps above
2. Run `python app.py`
3. Access at `http://localhost:5000`

#### Docker Deployment
1. Build the image:
```bash
docker build -t vote-system .
```

2. Run the container:
```bash
docker run -p 5000:5000 vote-system
```

#### Fly.io Deployment
1. Install Fly.io CLI
2. Login to Fly.io
3. Deploy:
```bash
fly launch
fly deploy
```

## Security Features

- Unique voting tokens
- One-time use tokens
- Token expiration
- Secure session management
- HTTPS enforcement

## Database Schema

### Tables
- `tokens`: Stores voting tokens
- `votes`: Records cast votes
- `options`: Available voting options

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 