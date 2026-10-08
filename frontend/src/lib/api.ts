export async function api(path: string, token?: string) {
  const r = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!r.ok) throw new Error(`${r.status} ${path}`)
  return r.json()
}
