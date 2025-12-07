'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Trash2, ShoppingBag } from 'lucide-react'
import { loadStripe } from '@stripe/stripe-js'

interface Product {
  url: string
  productName: string
  companyName: string
  credibilityScore: number
  imageUrl: string
  price: number | null
  quantity: number
}

export default function CartPage() {
  const [cart, setCart] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [stripePromise, setStripePromise] = useState<Promise<any> | null>(null)
  const router = useRouter()

  useEffect(() => {
    // Only initialize Stripe on client side
    if (typeof window !== 'undefined') {
      const stripeKey = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || 
        'pk_test_51SbXPE0K3XOps5QbYVMg7hm4ro7mZ3exjhTHFhqyjgE0SLJ230yWZQ7M10Q5hreqNAN2sYkEhlttzwvplmEcjIfd00tjkkU6t4'
      setStripePromise(loadStripe(stripeKey))
    }
    
    const cartData = JSON.parse(localStorage.getItem('cart') || '[]')
    setCart(cartData)
    setLoading(false)
  }, [])

  const removeFromCart = (url: string) => {
    const updatedCart = cart.filter(item => item.url !== url)
    setCart(updatedCart)
    localStorage.setItem('cart', JSON.stringify(updatedCart))
  }

  const updateQuantity = (url: string, quantity: number) => {
    if (quantity < 1) {
      removeFromCart(url)
      return
    }
    const updatedCart = cart.map(item =>
      item.url === url ? { ...item, quantity } : item
    )
    setCart(updatedCart)
    localStorage.setItem('cart', JSON.stringify(updatedCart))
  }

  const total = cart.reduce((sum, item) => {
    const price = (item.price !== null && item.price !== undefined && typeof item.price === 'number') ? item.price : 0
    return sum + price * (item.quantity || 1)
  }, 0)

  const handleCheckout = async () => {
    if (cart.length === 0) {
      alert('Your cart is empty!')
      return
    }

    try {
      console.log('Creating checkout session...', { itemCount: cart.length })
      
      const response = await fetch('http://localhost:5000/api/create-checkout-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ items: cart }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        console.error('Server error:', errorText)
        alert('Server error: ' + errorText)
        return
      }

      const data = await response.json()
      console.log('Checkout session response:', data)
      
      if (data.sessionId) {
        if (!stripePromise) {
          console.error('Stripe promise not initialized')
          alert('Stripe not initialized. Please refresh the page.')
          return
        }
        
        console.log('Loading Stripe...')
        const stripe = await stripePromise
        
        if (!stripe) {
          console.error('Stripe object is null')
          alert('Stripe not initialized. Please check your environment variables.')
          return
        }
        
        console.log('Redirecting to Stripe checkout...', { sessionId: data.sessionId })
        const { error } = await stripe.redirectToCheckout({
          sessionId: data.sessionId,
        })
        
        if (error) {
          console.error('Stripe redirect error:', error)
          alert('Error redirecting to checkout: ' + error.message)
        } else {
          console.log('Redirect initiated successfully')
        }
      } else {
        console.error('No session ID in response:', data)
        alert('Error: ' + (data.error || 'Failed to create checkout session'))
      }
    } catch (error) {
      console.error('Checkout error:', error)
      alert('Failed to connect to server. Make sure the Flask API is running. Error: ' + (error instanceof Error ? error.message : String(error)))
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading cart...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <div className="mb-6">
          <Button
            variant="ghost"
            onClick={() => router.push('/')}
            className="mb-4"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Search
          </Button>
          <h2 className="text-3xl font-bold text-gray-900">
            Shopping Cart
          </h2>
        </div>

        {cart.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <ShoppingBag className="mx-auto h-16 w-16 text-gray-400 mb-4" />
                <p className="text-gray-600 text-lg">Your cart is empty</p>
                <Button
                  onClick={() => router.push('/')}
                  className="mt-4"
                >
                  Start Shopping
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {cart.map((item, index) => (
                <Card key={index}>
                  <CardContent className="pt-6">
                    <div className="flex gap-4">
                      <div className="w-24 h-24 bg-gray-100 rounded-lg flex-shrink-0">
                        {item.imageUrl ? (
                          <img
                            src={item.imageUrl}
                            alt={item.productName}
                            className="w-full h-full object-contain rounded-lg"
                          />
                        ) : (
                          <div className="flex items-center justify-center h-full text-gray-400 text-xs">
                            No Image
                          </div>
                        )}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-lg mb-1">{item.productName}</h3>
                        <p className="text-gray-600 text-sm mb-2">{item.companyName}</p>
                        {item.price !== null && item.price !== undefined && typeof item.price === 'number' && (
                          <p className="text-xl font-bold text-purple-600 mb-3">
                            {item.price.toFixed(2)} RON
                          </p>
                        )}
                        <div className="flex items-center gap-4">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => updateQuantity(item.url, (item.quantity || 1) - 1)}
                            >
                              -
                            </Button>
                            <span className="w-8 text-center">{item.quantity || 1}</span>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => updateQuantity(item.url, (item.quantity || 1) + 1)}
                            >
                              +
                            </Button>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeFromCart(item.url)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            <div className="lg:col-span-1">
              <Card className="sticky top-4">
                <CardHeader>
                  <CardTitle>Order Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex justify-between text-lg">
                    <span>Subtotal:</span>
                    <span className="font-bold">{total.toFixed(2)} RON</span>
                  </div>
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>Items:</span>
                    <span>{cart.reduce((sum, item) => sum + (item.quantity || 1), 0)}</span>
                  </div>
                  <div className="border-t pt-4">
                    <div className="flex justify-between text-xl font-bold mb-4">
                      <span>Total:</span>
                      <span className="text-purple-600">{total.toFixed(2)} RON</span>
                    </div>
                    <Button
                      onClick={handleCheckout}
                      className="w-full bg-purple-600 hover:bg-purple-700"
                      size="lg"
                    >
                      Proceed to Checkout
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

