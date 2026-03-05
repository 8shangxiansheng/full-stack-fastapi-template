import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { ShoppingCart } from "lucide-react"
import { Suspense } from "react"

import { CartService, MenuService } from "@/client"
import PendingItems from "@/components/Pending/PendingItems"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type MenuDish = {
  id: string
  category_id: string
  name: string
  description?: string | null
  skus: Array<{
    id: string
    name: string
    price: string
    stock: number
    is_active: boolean
  }>
}

type MenuData = {
  categories: Array<{
    id: string
    name: string
    sort_order: number
  }>
  dishes: MenuDish[]
}

function getMenuQueryOptions() {
  return {
    queryFn: async (): Promise<MenuData> => {
      const [categories, dishes] = await Promise.all([
        MenuService.readCategories({ isActive: true }),
        MenuService.readDishesWithSkus({ isActive: true, skip: 0, limit: 100 }),
      ])
      return { categories, dishes: dishes as MenuDish[] }
    },
    queryKey: ["menu"],
  }
}

export const Route = createFileRoute("/_layout/items")({
  component: MenuPage,
  head: () => ({
    meta: [
      {
        title: "Menu - FastAPI Template",
      },
    ],
  }),
})

function MenuContent() {
  const queryClient = useQueryClient()
  const { showErrorToast, showSuccessToast } = useCustomToast()
  const { data } = useSuspenseQuery(getMenuQueryOptions())

  const addToCartMutation = useMutation({
    mutationFn: (dishSkuId: string) =>
      CartService.addCartItem({
        requestBody: {
          dish_sku_id: dishSkuId,
          quantity: 1,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Added to cart")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["cart"] })
    },
  })

  if (data.dishes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <ShoppingCart className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No menu is available yet</h3>
        <p className="text-muted-foreground">
          Ask admin to publish dishes first
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {data.categories.map((category) => {
        const categoryDishes = data.dishes.filter(
          (dish) => dish.category_id === category.id,
        )
        if (categoryDishes.length === 0) {
          return null
        }

        return (
          <section key={category.id} className="space-y-3">
            <h2 className="text-xl font-semibold">{category.name}</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {categoryDishes.map((dish) => (
                <div
                  key={dish.id}
                  className="rounded-lg border bg-card p-4 text-card-foreground space-y-3"
                >
                  <div className="space-y-1">
                    <h3 className="font-semibold text-base">{dish.name}</h3>
                    {dish.description ? (
                      <p className="text-sm text-muted-foreground">
                        {dish.description}
                      </p>
                    ) : null}
                  </div>

                  <div className="space-y-2">
                    {dish.skus.map((sku) => (
                      <div
                        key={sku.id}
                        className="flex items-center justify-between rounded-md border p-3"
                      >
                        <div className="space-y-1">
                          <p className="text-sm font-medium">{sku.name}</p>
                          <div className="flex items-center gap-2">
                            <Badge variant="secondary">¥ {sku.price}</Badge>
                            <span className="text-xs text-muted-foreground">
                              Stock: {sku.stock}
                            </span>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          onClick={() => addToCartMutation.mutate(sku.id)}
                          disabled={
                            addToCartMutation.isPending || sku.stock <= 0
                          }
                        >
                          Add
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function MenuTable() {
  return (
    <Suspense fallback={<PendingItems />}>
      <MenuContent />
    </Suspense>
  )
}

function MenuPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Menu</h1>
          <p className="text-muted-foreground">
            Browse dishes and add them to your cart
          </p>
        </div>
      </div>
      <MenuTable />
    </div>
  )
}
