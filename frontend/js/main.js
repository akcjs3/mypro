// =============================
// 현재 로그인 유저 정보 읽기 (localStorage)
// =============================
function getCurrentUser() {
  try {
    const raw = localStorage.getItem("ms_user");
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    console.error("ms_user 파싱 오류:", e);
    return null;
  }
}

let currentUser = getCurrentUser();
let isLoggedIn = !!currentUser;
let orbScrollHandlerAttached = false;  // ✅ orb 스크롤 핸들러 부착 여부


// =============================
// DOM 요소들
// =============================
const loginBtn = document.getElementById("login-btn");
const logoutBtn = document.getElementById("logout-btn");
const mypageBtn = document.getElementById("mypage-btn");
const nicknameLabel = document.getElementById("user-nickname-label"); // ✅ 추가
const aboutOrb = document.getElementById("about-orb");  // ✅ 추가

const navLinks = document.querySelectorAll(".nav-link");
const heroCard = document.querySelector(".hero-card");
const heroButtons = document.querySelectorAll(".hero-btn");

//녹화 중
const timerLabel = document.querySelector(".test-timer-label");
const timerDisplay = document.querySelector(".test-timer-display");
const testRunning = document.getElementById("test-running");


// 로그인 필요 모달 관련
const loginModalBackdrop = document.getElementById("login-modal-backdrop");
const loginModalCancel = document.getElementById("login-modal-cancel");
const loginModalGo = document.getElementById("login-modal-go");

// 소개는 누구나 가능, 나머지는 로그인 필요
const LOGIN_REQUIRED_PAGES = ["test", "ranking", "contact", "mypage"];

// =============================
// 헤더 UI 업데이트
// =============================
function updateAuthUI() {
  if (!loginBtn || !logoutBtn || !mypageBtn) return;

  isLoggedIn = !!currentUser;

  if (isLoggedIn) {
    // 로그인 상태
    loginBtn.classList.add("hidden");
    logoutBtn.classList.remove("hidden");
    mypageBtn.classList.remove("hidden");

    if (nicknameLabel) {
      nicknameLabel.classList.remove("hidden");
      nicknameLabel.textContent = currentUser?.nickname
        ? `${currentUser.nickname}님`
        : "";
    }
  } else {
    // 로그아웃 상태
    loginBtn.classList.remove("hidden");
    logoutBtn.classList.add("hidden");
    mypageBtn.classList.add("hidden");

    if (nicknameLabel) {
      nicknameLabel.classList.add("hidden");
      nicknameLabel.textContent = "";
    }
  }
}

// =============================
// 로그인 / 로그아웃 / 마이페이지 버튼
// =============================

// 로그인 버튼 → 로그인 페이지로 이동
if (loginBtn) {
  loginBtn.addEventListener("click", () => {
    window.location.href = "/login.html";
  });
}

// 로그아웃 버튼 → localStorage 비우고 메인으로
if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("ms_user");
    currentUser = null;
    updateAuthUI();
    window.location.href = "/"; // 메인으로
  });
}
// =============================
// 소개 모드 on/off
// =============================
function enterAboutMode() {
  const heroCard = document.querySelector(".hero-card");
  if (!heroCard) return;

  document.body.classList.add("about-mode");
  heroCard.classList.add("about-expanded");

  if (aboutOrb) {
    aboutOrb.classList.remove("hidden");
  }

  // ✅ 스크롤 핸들러 연결 (한 번만)
  if (!orbScrollHandlerAttached) {
    window.addEventListener("scroll", handleOrbScroll);
    orbScrollHandlerAttached = true;
  }
  // 진입 시 한 번 위치 계산
  handleOrbScroll();
}
// 스크롤에 따라 orb를 살짝 "낙하"시키는 함수
function handleOrbScroll() {
  if (!aboutOrb) return;
  if (!document.body.classList.contains("about-mode")) return;

  const maxOffset = 80;   // 최대 아래로 내려갈 거리(px) - 원하면 60~100 사이로 조절
  const maxScroll = 400;  // 이 정도 스크롤까지 점점 떨어지고, 그 이후로는 고정

  const scrollTop = window.scrollY || document.documentElement.scrollTop || 0;
  const progress = Math.min(scrollTop / maxScroll, 1); // 0 ~ 1
  const offset = progress * maxOffset;

  // 기본 위치(세로 중앙)에서 offset 만큼 아래로
  aboutOrb.style.transform = `translateY(-50%) translateY(${offset}px) scale(1)`;
}

function exitAboutMode() {
  const heroCard = document.querySelector(".hero-card");
  if (!heroCard) return;

  document.body.classList.remove("about-mode");
  heroCard.classList.remove("about-expanded");

  if (aboutOrb) {
    aboutOrb.classList.add("hidden");
    // transform 초기화 (CSS 기본값으로 복귀)
    aboutOrb.style.transform = "";
  }

  // ✅ 소개 모드 끝날 때 스크롤 핸들러 제거
  if (orbScrollHandlerAttached) {
    window.removeEventListener("scroll", handleOrbScroll);
    orbScrollHandlerAttached = false;
  }
}
if (aboutOrb) {
  aboutOrb.addEventListener("click", () => {
    exitAboutMode();
    // 소개 박스 위로 부드럽게 올라가기
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  });
}

// 마이페이지 버튼 → 로그인 필요
if (mypageBtn) {
  mypageBtn.addEventListener("click", () => {
    handleNavigate("mypage");
  });
}

// =============================
// 로그인 필요 모달 열기/닫기
// =============================
function openLoginRequiredModal() {
  if (!loginModalBackdrop) return;
  loginModalBackdrop.classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function closeLoginRequiredModal() {
  if (!loginModalBackdrop) return;
  loginModalBackdrop.classList.add("hidden");
  document.body.classList.remove("modal-open");
}

if (loginModalCancel) {
  loginModalCancel.addEventListener("click", () => {
    closeLoginRequiredModal();
  });
}

if (loginModalGo) {
  loginModalGo.addEventListener("click", () => {
    window.location.href = "/login.html";
  });
}

// =============================
// 페이지 이동 공통 처리
// =============================
function handleNavigate(page) {
  // ✅ 소개는 언제나 로그인 없이 가능
  if (page === "about") {
    // 메인(index)에서만 애니메이션 모드 사용
    if (window.location.pathname === "/" || window.location.pathname.endsWith("index.html")) {
      enterAboutMode();   // 소개 모드 진입 (hero 커지고 내용 사라짐)
    } else {
      // 다른 페이지(test, ranking 등)에서 소개 누르면 메인으로 보내기
      window.location.href = "/";
    }
    return;
  }

  // 소개가 아닌 다른 페이지로 갈 때는 소개 모드 해제
  exitAboutMode();

  // 로그인 필요한 페이지인데, 로그인 안 돼 있으면 모달
  if (!isLoggedIn && LOGIN_REQUIRED_PAGES.includes(page)) {
    openLoginRequiredModal();
    return;
  }

  // 로그인 상태면 실제 페이지로 이동
  switch (page) {
    case "test":
      window.location.href = "/test.html";
      break;
    case "ranking":
      window.location.href = "/ranking.html";
      break;
    case "contact":
      window.location.href = "/contact.html";
      break;
    case "mypage":
      window.location.href = "/mypage.html";
      break;
    default:
      console.log("알 수 없는 page:", page);
  }
}


// =============================
// 상단 네비게이션 클릭 처리
// =============================
navLinks.forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();

    const page = link.dataset.page;
    if (!page) return;

    // active 표시 (지금 페이지에선 시각적 효과용)
    navLinks.forEach((l) => l.classList.remove("is-active"));
    link.classList.add("is-active");

    handleNavigate(page);
  });
});

countdownTimer = setInterval(() => {
  remainingMs -= 10;
  if (remainingMs <= 0) {
    remainingMs = 0;
    updateTimerDisplays();
    clearInterval(countdownTimer);
    countdownTimer = null;
    isTesting = true;
    console.log("✅ 여기서 실제 검사 시작 (퍼지 로직 연동 예정)");

    // ✅ 타이머/문구 숨기고, 검사중 UI 켜기
    if (timerLabel) timerLabel.classList.add("hidden");
    if (timerDisplay) timerDisplay.classList.add("hidden");
    if (testRunning) testRunning.classList.remove("hidden");

    return;
  }
  updateTimerDisplays();
}, 10);

function resetTestState() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  remainingMs = 10000;
  updateTimerDisplays();

  if (testStartBtn && testStopBtn) {
    testStartBtn.disabled = false;
    testStopBtn.disabled = true;
  }
  isTesting = false;

  // ✅ 검사중 UI 끄고, 타이머/문구 다시 보이게
  if (timerLabel) timerLabel.classList.remove("hidden");
  if (timerDisplay) timerDisplay.classList.remove("hidden");
  if (testRunning) testRunning.classList.add("hidden");

  console.log("[test] 검사/카운트다운 초기화");
}



// =============================
// 중앙 카드 hover 인터랙션 (버튼 등장)
// =============================
if (heroCard) {
  heroCard.addEventListener("mouseenter", () => {
    heroCard.classList.add("is-active");
  });

  heroCard.addEventListener("mouseleave", () => {
    heroCard.classList.remove("is-active");
  });
}

// =============================
// 중앙 카드 안 버튼 (검사/랭킹/소개/문의)
// =============================
heroButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const page = btn.dataset.page;
    if (!page) return;

    handleNavigate(page);
  });
});

// =============================
// 초기 UI 반영
// =============================
updateAuthUI();
