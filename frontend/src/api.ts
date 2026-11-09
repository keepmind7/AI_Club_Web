function csrfToken() {
  return document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/)?.[1] ?? ''
}

function send(path: string, method: 'GET' | 'POST', body?: unknown) {
  return fetch(path, {
    method,
    credentials: 'same-origin',
    headers: method === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

// 같은 출처의 /api/... 호출. 실패하면 응답의 detail을 메시지로 던진다.
export async function api<T>(path: string, method: 'GET' | 'POST' = 'GET', body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await send(path, method, body)
  } catch {
    throw new Error('서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요.')
  }
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (res.ok) return data as T
  const message: string = data?.detail ?? `요청을 처리하지 못했어요. 잠시 뒤 다시 시도해 주세요. (${res.status})`
  // 계약에 오류 코드 필드가 없어, 비로그인 403과 휴면·탈퇴 403은 백엔드 안내 문구("이용이 제한된 계정이에요. 운영진에게 문의해 주세요.")로만 구분된다.
  const restricted = res.status === 403 && message.includes('이용이 제한')
  if (restricted && path !== '/api/auth/login') {
    // 세션을 끊어야 다음 /api/auth/me가 다시 403을 주지 않는다. 이미 같은 안내 화면이면 새로 불러오지 않는다(반복 방지).
    await send('/api/auth/logout', 'POST').catch(() => {})
    const target = '/login?reason=' + encodeURIComponent(message)
    if (location.pathname + location.search !== target) {
      location.assign(target)
      // 페이지를 떠나는 중이다. 라우터 가드가 /login으로 먼저 이동해 위 이동을 덮지 않도록 끝나지 않는 Promise를 돌려준다.
      return new Promise<T>(() => {})
    }
  } else if ((res.status === 401 || res.status === 403) && !path.startsWith('/api/auth/')) {
    // 로그인 API 오류는 화면이 직접 보여 준다. 세션 만료 등 나머지 401/403은 로그인 화면으로.
    location.assign('/login')
  }
  throw new Error(message)
}
