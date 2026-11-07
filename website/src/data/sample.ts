// Every person, email, phone and amount here is made up for the page.
// 555-01xx numbers and example.com / example.org addresses are reserved for fiction.

export type RecordId = 'a' | 'b' | 'c'

export const records = [
  { id: 'a', name: 'Rosa Delgado', email: 'rosa.delgado@example.com', phone: '(305) 555-0142', source: 'Online donations', mark: 'ONLINE DONATIONS' },
  { id: 'b', name: 'Rosa M. Delgado', email: 'rosa.delgado@example.com', phone: 'No phone on file', source: 'Gala auction', mark: 'GALA AUCTION' },
  { id: 'c', name: 'R. Delgado', email: 'rdelgado@example.org', phone: '(305) 555-0142', source: 'Checks in the mail', mark: 'CHECKS BY MAIL' },
] as const

export const gifts: { record: RecordId; source: string; date: string; amount: number }[] = [
  { record: 'a', source: 'Online', date: 'Oct 2, 2026', amount: 50 },
  { record: 'a', source: 'Online', date: 'Sep 2, 2026', amount: 50 },
  { record: 'a', source: 'Online', date: 'Aug 2, 2026', amount: 50 },
  { record: 'b', source: 'Auction', date: 'Mar 14, 2026', amount: 320 },
  { record: 'c', source: 'Check', date: 'Dec 11, 2025', amount: 250 },
  { record: 'c', source: 'Check', date: 'Dec 9, 2024', amount: 250 },
]

export const totalFor = (id: RecordId) =>
  gifts.filter(g => g.record === id).reduce((sum, g) => sum + g.amount, 0)
export const giftTotal = gifts.reduce((sum, g) => sum + g.amount, 0)
export const money = (n: number) => `$${n.toLocaleString('en-US')}`

export const reasons = ['Same last name', 'First name fits', 'Same phone on 2 records', 'Different emails: kept both']

// The four lists as they arrive. `rosa` marks the rows that are secretly one person.
export const lists = [
  { title: 'Online donation page', rows: [['Rosa Delgado', 50, true], ['Tom Ferris', 25, false], ['Lena Ortiz', 100, false]] },
  { title: 'Event tickets', rows: [['Tom Ferris', 75, false], ['Ana Ruiz', 75, false], ['D. Okafor', 75, false]] },
  { title: 'Gala auction', rows: [['Lena Ortiz', 140, false], ['Rosa M. Delgado', 320, true], ['D. Okafor', 90, false]] },
  { title: 'Checks in the mail', rows: [['Marcus Bell', 250, false], ['R. Delgado', 250, true], ['Priya Nair', 100, false]] },
] as { title: string; rows: [string, number, boolean][] }[]

export const files = [
  { name: 'Online donations', file: 'online-donations.csv', rows: 214 },
  { name: 'Event tickets', file: 'event-tickets.csv', rows: 96 },
  { name: 'Gala auction', file: 'gala-auction.csv', rows: 41 },
  { name: 'Checks in the mail', file: 'checks-typed-in.csv', rows: 73 },
]
export const fileRowTotal = files.reduce((sum, f) => sum + f.rows, 0)

export const compare = [
  { field: 'Name', left: 'Rosa Delgado', right: 'R. Delgado', verdict: 'First name fits', same: true },
  { field: 'Phone', left: '(305) 555-0142', right: '(305) 555-0142', verdict: 'Same', same: true },
  { field: 'Email', left: 'rosa.delgado@example.com', right: 'rdelgado@example.org', verdict: 'Different. Keeps both', same: false },
]

export const lateDonors = [
  { name: 'Marcus Bell', last: 'Dec 12, 2024', amount: 250, timing: 'Every December', status: 'Late: no gift last December', late: true },
  { name: 'Ana Ruiz', last: 'Aug 3, 2026', amount: 25, timing: 'Monthly, around the 3rd', status: 'Late: 2 months', late: true },
  { name: 'Priya Nair', last: 'Oct 18, 2026', amount: 100, timing: 'Every October', status: 'On time', late: false },
]

export const noteDonor = lateDonors[0]
export const noteText =
  "Hi Marcus, thank you for your gift in December 2024. It went to kids and families here in Miami-Dade. We haven't talked since, and I wanted to say hello and see how you're doing. Could I give you a quick call this week?"
export const noteSign = 'Denise, Tidepath Family Alliance'

export const monthly = [
  { month: 'Jun', ok: true }, { month: 'Jul', ok: true }, { month: 'Aug', ok: true },
  { month: 'Sep', ok: true }, { month: 'Oct', ok: true }, { month: 'Nov', ok: false },
]
