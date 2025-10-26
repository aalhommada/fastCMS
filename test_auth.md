# Authentication API Test Examples

## 1. Register a New User

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123",
    "password_confirm": "password123",
    "name": "John Doe"
  }'
```

**Response:**
```json
{
  "user": {
    "id": "uuid-here",
    "email": "user@example.com",
    "verified": false,
    "name": "John Doe",
    "avatar": null,
    "created": "2025-10-26T...",
    "updated": "2025-10-26T..."
  },
  "token": {
    "access_token": "eyJhbGc...",
    "refresh_token": "eyJhbGc...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

## 2. Login

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

## 3. Get Current User (Requires Auth)

```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 4. Refresh Access Token

```bash
curl -X POST "http://localhost:8000/api/v1/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

## 5. Update User Profile

```bash
curl -X PATCH "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "email_visibility": true
  }'
```

## 6. Change Password

```bash
curl -X POST "http://localhost:8000/api/v1/auth/change-password" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "password123",
    "new_password": "newpassword456",
    "new_password_confirm": "newpassword456"
  }'
```

## 7. Logout (Single Device)

```bash
curl -X POST "http://localhost:8000/api/v1/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

## 8. Logout All Devices

```bash
curl -X POST "http://localhost:8000/api/v1/auth/logout-all" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Using with JavaScript

```javascript
// Register
const registerResponse = await fetch('http://localhost:8000/api/v1/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'password123',
    password_confirm: 'password123',
    name: 'John Doe'
  })
});

const { user, token } = await registerResponse.json();

// Store tokens
localStorage.setItem('access_token', token.access_token);
localStorage.setItem('refresh_token', token.refresh_token);

// Make authenticated request
const profileResponse = await fetch('http://localhost:8000/api/v1/auth/me', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  }
});

const profile = await profileResponse.json();
```

## Using with Python

```python
import requests

# Register
response = requests.post('http://localhost:8000/api/v1/auth/register', json={
    'email': 'user@example.com',
    'password': 'password123',
    'password_confirm': 'password123',
    'name': 'John Doe'
})

data = response.json()
access_token = data['token']['access_token']
refresh_token = data['token']['refresh_token']

# Make authenticated request
headers = {'Authorization': f'Bearer {access_token}'}
profile = requests.get('http://localhost:8000/api/v1/auth/me', headers=headers)
print(profile.json())
```

## Testing Collections with Auth

```bash
# Create a collection (requires authentication)
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "articles",
    "type": "base",
    "schema": [
      {
        "name": "title",
        "type": "text",
        "validation": {"required": true}
      },
      {
        "name": "content",
        "type": "editor"
      }
    ],
    "create_rule": "@request.auth.id != \"\"",
    "update_rule": "@request.auth.id != \"\"",
    "delete_rule": "@request.auth.id != \"\""
  }'
```

## Password Requirements

- Minimum 8 characters
- Must contain at least one letter
- Must contain at least one number

## Token Expiry

- **Access Token:** 15 minutes (configurable in .env)
- **Refresh Token:** 30 days (configurable in .env)

## Security Features

- ✅ Bcrypt password hashing (cost factor 12)
- ✅ JWT token-based authentication
- ✅ Refresh token rotation
- ✅ Token key for session invalidation
- ✅ Multiple device session tracking
- ✅ IP address and user agent logging
