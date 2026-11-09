import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './auth'
import Attendance from './pages/Attendance.vue'
import ChangePassword from './pages/ChangePassword.vue'
import Dashboard from './pages/Dashboard.vue'
import EventDetail from './pages/EventDetail.vue'
import Events from './pages/Events.vue'
import Home from './pages/Home.vue'
import Login from './pages/Login.vue'
import Me from './pages/Me.vue'
import News from './pages/News.vue'
import Payments from './pages/Payments.vue'
import PostDetail from './pages/PostDetail.vue'
import PostForm from './pages/PostForm.vue'
import SharedAccounts from './pages/SharedAccounts.vue'
import Signup from './pages/Signup.vue'
import Staff from './pages/Staff.vue'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    staff?: boolean
    tab?: 'home' | 'events' | 'news' | 'me' | 'staff' // 하위 화면에서도 강조할 메뉴
    ownBar?: boolean // 화면이 자기 하단 고정 바를 가져 휴대폰에서 탭바를 숨긴다
  }
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/signup', component: Signup, meta: { public: true } },
    { path: '/password', component: ChangePassword, meta: { tab: 'me' } },
    { path: '/', component: Home, meta: { tab: 'home' } },
    { path: '/events', component: Events, meta: { tab: 'events' } },
    { path: '/events/:id', component: EventDetail, props: true, meta: { tab: 'events', ownBar: true } },
    { path: '/news', component: News, meta: { tab: 'news' } },
    { path: '/announcements', redirect: '/news?tab=notice' },
    { path: '/board', redirect: '/news?tab=board' },
    { path: '/board/new', component: PostForm, meta: { tab: 'news', ownBar: true } },
    { path: '/board/:id', component: PostDetail, props: true, meta: { tab: 'news', ownBar: true } },
    { path: '/board/:id/edit', component: PostForm, props: true, meta: { tab: 'news', ownBar: true } },
    { path: '/me', component: Me, meta: { tab: 'me' } },
    { path: '/attendance', component: Attendance, meta: { tab: 'me' } },
    { path: '/payments', component: Payments, meta: { tab: 'me' } },
    { path: '/shared-accounts', component: SharedAccounts, meta: { tab: 'me' } },
    { path: '/staff', component: Staff, meta: { tab: 'staff', staff: true } },
    { path: '/dashboard', component: Dashboard, meta: { tab: 'staff', staff: true } },
    { path: '/:rest(.*)*', redirect: '/' },
  ],
  // 새 화면은 맨 위에서, 뒤로 가기는 보던 위치에서. 대시보드 #구역 이동은 데이터를 받은 뒤 화면이 직접 한다.
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.loaded) await auth.load()
  if (to.meta.public) return to.path === '/signup' && auth.user ? '/' : true
  if (!auth.user) return '/login'
  if (auth.user.must_change_password && to.path !== '/password') return '/password'
  if (to.meta.staff && !auth.user.is_staff) return '/'
  return true
})
