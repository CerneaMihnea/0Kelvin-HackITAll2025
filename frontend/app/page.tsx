'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Search, Loader2, ShoppingCart, History, ExternalLink, Send, Bot, User } from 'lucide-react'

interface Product {
  url: string
  productName: string
  companyName: string
  credibilityScore: number
  imageUrl: string
  price: number | null
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export default function Home() {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [products, setProducts] = useState<Product[]>([])
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I\'m your AI shopping assistant. Tell me what you\'re looking for and I\'ll help you find products from local companies.',
      timestamp: new Date()
    }
  ])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const router = useRouter()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const addToCart = (product: Product) => {
    const cart = JSON.parse(localStorage.getItem('cart') || '[]')
    const existingIndex = cart.findIndex((item: Product) => item.url === product.url)
    
    if (existingIndex >= 0) {
      cart[existingIndex].quantity = (cart[existingIndex].quantity || 1) + 1
    } else {
      cart.push({ ...product, quantity: 1 })
    }
    
    localStorage.setItem('cart', JSON.stringify(cart))
    alert('Product added to cart!')
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-50 border-green-200'
    if (score >= 60) return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    return 'text-red-600 bg-red-50 border-red-200'
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim() || loading) return

    const userMessage = prompt.trim()
    setPrompt('')
    setLoading(true)

    // Add user message to conversation
    setMessages(prev => [...prev, {
      role: 'user',
      content: userMessage,
      timestamp: new Date()
    }])

    // Add loading message
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: 'Searching for products...',
      timestamp: new Date()
    }])

    try {
      const response = await fetch('http://localhost:5000/api/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt: userMessage }),
      })

      const data = await response.json()
      
      if (data.success) {
        setProducts(data.products)
        
        // Remove loading message and add response
        setMessages(prev => {
          const newMessages = prev.slice(0, -1) // Remove loading message
          return [...newMessages, {
            role: 'assistant',
            content: `I found ${data.products.length} products matching your search! Check them out on the right.`,
            timestamp: new Date()
          }]
        })
      } else {
        setMessages(prev => {
          const newMessages = prev.slice(0, -1)
          return [...newMessages, {
            role: 'assistant',
            content: 'Sorry, I encountered an error: ' + (data.error || 'Failed to search products'),
            timestamp: new Date()
          }]
        })
      }
    } catch (error) {
      console.error('Error:', error)
      setMessages(prev => {
        const newMessages = prev.slice(0, -1)
        return [...newMessages, {
          role: 'assistant',
          content: 'Failed to connect to server. Make sure the Flask API is running.',
          timestamp: new Date()
        }]
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Local Goods</h1>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push('/cart')}
          >
            <ShoppingCart className="mr-2 h-4 w-4" />
            Cart
          </Button>
          <Button
            variant="outline"
            onClick={() => router.push('/history')}
          >
            <History className="mr-2 h-4 w-4" />
            Recent Searches
          </Button>
        </div>
      </div>

      {/* Main Content - Split Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Side - AI Conversation */}
        <div className="w-1/2 border-r border-gray-200 flex flex-col bg-white">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Bot className="h-5 w-5 text-blue-600" />
              AI Shopping Assistant
            </h2>
          </div>
          
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex gap-3 ${
                  message.role === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.role === 'assistant' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                    <Bot className="h-4 w-4 text-blue-600" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                >
                  <p className="text-sm">{message.content}</p>
                </div>
                {message.role === 'user' && (
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                    <User className="h-4 w-4 text-gray-600" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-3 justify-start">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-blue-600" />
                </div>
                <div className="bg-gray-100 rounded-lg px-4 py-2">
                  <Loader2 className="h-4 w-4 animate-spin text-gray-600" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Form */}
          <div className="p-4 border-t border-gray-200">
            <form onSubmit={handleSearch} className="flex gap-2">
              <Input
                type="text"
                placeholder="Describe what you're looking for..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="flex-1"
                disabled={loading}
              />
              <Button
                type="submit"
                disabled={loading || !prompt.trim()}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </form>
          </div>
        </div>

        {/* Right Side - Products */}
        <div className="w-1/2 overflow-y-auto bg-gray-50">
          <div className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Products {products.length > 0 && `(${products.length})`}
            </h2>
            
            {products.length === 0 ? (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center py-12">
                    <Search className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                    <p className="text-gray-600">
                      Start a conversation to search for products
                    </p>
                  </div>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {products.map((product, index) => (
                  <Card key={index} className="overflow-hidden hover:shadow-lg transition-shadow">
                    <div className="flex gap-4">
                      <div className="w-32 h-32 bg-gray-100 rounded-lg flex-shrink-0">
                        {product.imageUrl ? (
                          <img
                            src={product.imageUrl}
                            alt={product.productName}
                            className="w-full h-full object-contain rounded-lg"
                            onError={(e) => {
                              const target = e.target as HTMLImageElement
                              target.style.display = 'none'
                            }}
                          />
                        ) : (
                          <div className="flex items-center justify-center h-full text-gray-400 text-xs">
                            No Image
                          </div>
                        )}
                      </div>
                      <div className="flex-1 p-4">
                        <CardTitle className="text-base mb-1 line-clamp-2">
                          {product.productName}
                        </CardTitle>
                        <CardDescription className="text-sm mb-2">
                          {product.companyName}
                        </CardDescription>
                        {product.price !== null && product.price !== undefined && typeof product.price === 'number' && (
                          <p className="text-xl font-bold text-blue-600 mb-2">
                            {product.price.toFixed(2)} RON
                          </p>
                        )}
                        <div className="flex items-center justify-between">
                          <div className={`px-3 py-1 rounded-lg border-2 font-semibold text-sm ${getScoreColor(product.credibilityScore)}`}>
                            {product.credibilityScore}%
                          </div>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => window.open(product.url, '_blank')}
                            >
                              <ExternalLink className="mr-2 h-3 w-3" />
                              View
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => addToCart(product)}
                              className="bg-blue-600 hover:bg-blue-700"
                            >
                              <ShoppingCart className="mr-2 h-3 w-3" />
                              Add
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

