import { expect, test as setup } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "./config.ts"

const authFile = "playwright/.auth/user.json"

setup("authenticate", async ({ page, request }) => {
  const loginResponse = await request.post(
    `${process.env.VITE_API_URL}/api/v1/login/access-token`,
    {
      form: {
        username: firstSuperuser,
        password: firstSuperuserPassword,
      },
    },
  )
  expect(loginResponse.ok()).toBeTruthy()
  const loginData = await loginResponse.json()

  await page.goto("/")
  await page.evaluate((token: string) => {
    localStorage.setItem("access_token", token)
  }, loginData.access_token)
  await page.context().storageState({ path: authFile })
})
