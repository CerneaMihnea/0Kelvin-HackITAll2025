'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ArrowLeft, CheckSquare, Square, ShoppingCart, ExternalLink } from 'lucide-react'

interface SearchHistoryItem {
  id: number
  prompt: string
  productCount: number
  timestamp: string
  selected?: boolean
}

interface Product {
  url: string
  productName: string
  companyName: string
  credibilityScore: number
  imageUrl: string
  price: number | null
  searchPrompt?: string
}

export default function HistoryPage() {
  const [history, setHistory] = useState<SearchHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loadingProducts, setLoadingProducts] = useState(false)
  const [showProducts, setShowProducts] = useState(false)
  const router = useRouter()

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/search-history')
      const data = await response.json()
      if (data.success) {
        setHistory(data.history)
        const selected = data.history.filter((item: SearchHistoryItem) => item.selected).map((item: SearchHistoryItem) => item.id)
        setSelectedIds(selected)
      }
    } catch (error) {
      console.error('Error loading history:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleSelection = (id: number) => {
    setSelectedIds(prev => {
      const newSelected = prev.includes(id)
        ? prev.filter(selectedId => selectedId !== id)
        : [...prev, id]
      return newSelected
    })
  }

  const saveSelection = async () => {
    try {
      // First save the selection
      const response = await fetch('http://localhost:5000/api/search-history', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ selectedIds: selectedIds }),
      })
      const data = await response.json()
      if (!data.success) {
        alert('Error saving selection')
        return
      }
      
      // Then fetch products for selected searches
      if (selectedIds.length > 0) {
        setLoadingProducts(true)
        setShowProducts(true)
        
        const selectedPrompts = history
          .filter(item => selectedIds.includes(item.id))
          .map(item => item.prompt)
        
        const productsResponse = await fetch('http://localhost:5000/api/search-history/products', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ prompts: selectedPrompts }),
        })
        
        const productsData = await productsResponse.json()
        if (productsData.success) {
          setProducts(productsData.products)
        } else {
          alert('Error loading products')
        }
        setLoadingProducts(false)
      } else {
        setShowProducts(false)
        setProducts([])
      }
      
      loadHistory()
    } catch (error) {
      console.error('Error saving selection:', error)
      alert('Failed to save selection')
      setLoadingProducts(false)
    }
  }

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

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading history...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="mb-6">
          <Button
            variant="ghost"
            onClick={() => router.push('/')}
            className="mb-4"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Search
          </Button>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-3xl font-bold text-gray-900">
                Recent Searches
              </h2>
              <p className="text-gray-600 mt-2">
                Select which searches you want to show
              </p>
            </div>
            <Button
              onClick={saveSelection}
              className="bg-blue-600 hover:bg-blue-700"
            >
              Save Selection
            </Button>
          </div>
        </div>

        {showProducts && (
          <div className="mb-8">
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              Products from Selected Searches ({products.length})
            </h3>
            {loadingProducts ? (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600">Loading products...</p>
              </div>
            ) : products.length === 0 ? (
              <Card>
                <CardContent className="pt-6">
                  <p className="text-center text-gray-600">
                    No products found for selected searches.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {products.map((product, index) => (
                  <Card key={index} className="overflow-hidden hover:shadow-lg transition-shadow flex flex-col">
                    <div className="relative h-64 w-full bg-gray-100 flex-shrink-0">
                      {product.imageUrl ? (
                        <img
                          src={product.imageUrl}
                          alt={product.productName}
                          className="w-full h-full object-contain"
                          onError={(e) => {
                            const target = e.target as HTMLImageElement
                            target.style.display = 'none'
                            const parent = target.parentElement
                            if (parent && !parent.querySelector('.placeholder')) {
                              const placeholder = document.createElement('div')
                              placeholder.className = 'placeholder flex items-center justify-center h-full text-gray-400'
                              placeholder.textContent = 'No Image'
                              parent.appendChild(placeholder)
                            }
                          }}
                        />
                      ) : (
                        <div className="flex items-center justify-center h-full text-gray-400">
                          No Image
                        </div>
                      )}
                    </div>
                    <CardHeader className="flex-shrink-0">
                      <CardTitle className="text-lg line-clamp-2 min-h-[3rem]">
                        {product.productName}
                      </CardTitle>
                      <CardDescription className="text-base">
                        {product.companyName}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex-1 flex flex-col justify-between">
                      <div className="space-y-3">
                        {product.price !== null && product.price !== undefined && typeof product.price === 'number' && (
                          <div className="text-2xl font-bold text-blue-600">
                            {product.price.toFixed(2)} RON
                          </div>
                        )}
                        <div className="flex items-center justify-between">
                          <div className={`px-4 py-2 rounded-lg border-2 font-bold text-lg ${getScoreColor(product.credibilityScore)}`}>
                            {product.credibilityScore}%
                          </div>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => window.open(product.url, '_blank')}
                            >
                              <ExternalLink className="mr-2 h-4 w-4" />
                              View
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => addToCart(product)}
                              className="bg-blue-600 hover:bg-blue-700"
                            >
                              <ShoppingCart className="mr-2 h-4 w-4" />
                              Add to Cart
                            </Button>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="mb-6">
          <h3 className="text-2xl font-bold text-gray-900 mb-4">Search History</h3>
        </div>

        {history.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <p className="text-center text-gray-600">
                No search history found.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {history.map((item) => {
              const isSelected = selectedIds.includes(item.id)
              return (
                <Card
                  key={item.id}
                  className={`cursor-pointer transition-all ${
                    isSelected ? 'border-blue-500 bg-blue-50' : ''
                  }`}
                  onClick={() => toggleSelection(item.id)}
                >
                  <CardContent className="pt-6">
                    <div className="flex items-start gap-4">
                      <div className="mt-1">
                        {isSelected ? (
                          <CheckSquare className="h-6 w-6 text-blue-600" />
                        ) : (
                          <Square className="h-6 w-6 text-gray-400" />
                        )}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-lg mb-2">{item.prompt}</h3>
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <span>{item.productCount} products found</span>
                          <span>•</span>
                          <span>{formatDate(item.timestamp)}</span>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

