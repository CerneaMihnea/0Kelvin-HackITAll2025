# Setup Instructions

## Backend Setup

1. Install Python dependencies:
```bash
pip install -r requirments.txt
```

2. Set up Stripe:
   - Sign up at https://stripe.com
   - Get your API keys from https://dashboard.stripe.com/apikeys
   - Set environment variable:
   ```bash
   export STRIPE_SECRET_KEY=sk_test_your_secret_key_here
   ```
   Or create a `.env` file in the root directory:
   ```
   STRIPE_SECRET_KEY=sk_test_your_secret_key_here
   ```

3. Run the Flask API:
```bash
python flask_api.py
```

The API will run on `http://localhost:5000`

## Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create a `.env.local` file in the `frontend` directory:
```
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
```

4. Run the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

## Features Added

1. **Price Tags**: Products now display their prices extracted from eMAG product pages
2. **Shopping Cart**: 
   - Add products to cart from the results page
   - View cart with quantity management
   - Remove items from cart
3. **Stripe Payment Integration**:
   - Secure checkout with Stripe
   - Card payment processing
   - Success page after payment
4. **Recent Searches Page**:
   - View all recent searches
   - Select which searches to show
   - Save your selection preferences

## Usage

1. Search for products on the home page
2. View results with prices and credibility scores
3. Add products to cart
4. Go to cart to review and checkout
5. Complete payment with Stripe
6. View and manage recent searches in the History page

