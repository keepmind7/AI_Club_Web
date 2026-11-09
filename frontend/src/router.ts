import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './auth'
import Announcements from './pages/Announcements.vue'
import Attendance from './pages/Attendance.vue'
import Board from './pages/Board.vue'
import ChangePassword from './pages/ChangePassword.vue'
import Dashboard from './pages/Dashboard.vue'
import EventDetail from './pages/EventDetail.vue'
import Events from './pages/Events.vue'
import Home from './pages/Home.vue'
import Login from './pages/Login.vue'
import Me from './pages/Me.vue'
import Payments from './pages/Payments.vue'
import PostDetail from './pages/PostDetail.vue'
import PostForm from './pages/PostForm.vue'
import SharedAccounts from './pages/SharedAccounts.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/password', component: ChangePassword },
    { path: '/', component: Home },
    { path: '/events', component: Events },
    { path: '/events/:id', component: EventDetail, props: true },
    { path: '/attendance', component: Attendance },
    { path: '/payments', component: Payments },
    { path: '/announcements', component: Announcements },
    { path: '/board', component: Board },
    { path: '/board/new', component: PostForm },
    { path: '/board/:id', component: PostDetail, props: true },
    { path: '/board/:id/edit', component: PostForm, props: true },
    { path: '/me', component: Me },
    { path: '/shared-accounts', component: SharedAccounts },
    { path: '/dashboard', component: Dashboard, meta: { staff: true } },
    { path: '/:rest(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.loaded) await auth.load()
  if (to.meta.public) return true
  if (!auth.user) return '/login'
  if (auth.user.must_change_password && to.path !== '/password') return '/password'
  if (to.meta.staff && !auth.user.is_staff) return '/'
  return true
})
