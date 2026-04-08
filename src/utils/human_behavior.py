import random
import time
from datetime import datetime
import numpy as np

class HumanBehaviorModel:
    """
    Simulates non-deterministic human WhatsApp Web usage for passive group reading.
    Ensures behavioral entropy to avoid API bans based on deterministic polling.
    """
    def __init__(self):
        self.last_intervals = []
        self.null_sessions_today = 0
        self.last_null_session_date = None
        
        # Anti-pattern tracking for polling
        self.last_window_size = None
        self.last_count = None

    def get_next_interval(self) -> float:
        """
        Generate session entry intervals (ANTI-BAN THROTTLING).
        - Distribution: Log-Normal
        - Mean interval: 15-25 minutes (900-1500 seconds)
        - Hard min gap: 600 sec (10 minutes)
        - Hard max gap: 2400 sec (40 minutes)
        Avoids periodicity and repeating patterns. Prevents WHAPI rate-limits.
        """
        mean = random.uniform(900, 1500)
        sigma = 0.5 # Width of distribution
        
        while True:
            # log-normal parameters: mu and sigma
            mu = np.log(mean) - (sigma**2) / 2
            interval = np.random.lognormal(mean=mu, sigma=sigma)
            
            # Enforce hard limits
            if 600 <= interval <= 2400:
                # Avoid exact repeating patterns (crude check against last 3)
                if not any(abs(interval - x) < 30.0 for x in self.last_intervals):
                    break
        
        self.last_intervals.append(interval)
        if len(self.last_intervals) > 3:
            self.last_intervals.pop(0)
            
        return interval

    def get_session_duration(self) -> float:
        """
        Use Weibull distribution for session duration:
        - Min: 60 sec
        - Median target: 240 sec (Longer reading sessions)
        - Max: 480 sec
        """
        # Weibull distribution shape parameter
        shape = 1.5
        # Scale parameter approximating median 240 when shifted by min 60
        scale = 180 
        
        while True:
            duration = np.random.weibull(shape) * scale + 60
            if 60 <= duration <= 480:
                break
                
        return duration

    def should_exit_early(self) -> bool:
        """Random early exits allowed (p=0.22)"""
        return random.random() < 0.22

    def check_null_session(self) -> bool:
        """
        Inject 2-5 "null sessions" per day:
        - enter platform
        - no group access
        - exit within 15-35 sec
        """
        today = datetime.now().date()
        if self.last_null_session_date != today:
            self.null_sessions_today = 0
            self.last_null_session_date = today
            # Determine target for today
            self.target_null_sessions = random.randint(2, 5)

        if self.null_sessions_today < self.target_null_sessions:
            # Probability scaled by time left in day to spread them out
            # Simplified: just flat 5% chance until we hit the target
            if random.random() < 0.05:
                self.null_sessions_today += 1
                return True
        return False

    def get_null_session_duration(self) -> float:
        """Duration for null sessions: 15-35 seconds"""
        return random.uniform(15, 35)

    def get_target_group_count(self) -> int:
        """
        How many groups does the user check in this session?
        - 18% probability: access 0 target groups
        - Otherwise: 5 to 15 groups
        Since intervals are slower (10-40 min gaps), we read more groups per block.
        """
        # 18% null access
        if random.random() < 0.18:
            return 0
        return random.randint(5, 15)

    def should_open_non_target_chat(self) -> bool:
        """33% probability: open non-target chat preview"""
        return random.random() < 0.33
        
    def should_enter_then_exit_fast(self) -> bool:
        """21% probability: enter then exit within 3 sec"""
        return random.random() < 0.21

    # Chatter interaction logics
    def get_scroll_depth(self) -> float:
        """Random scroll depth: 15%-75% viewport"""
        return random.uniform(0.15, 0.75)

    def should_stop_mid_scroll(self) -> bool:
        """35% probability: stop mid-scroll"""
        return random.random() < 0.35

    def should_not_reach_latest(self) -> bool:
        """42% probability: do not reach latest message"""
        return random.random() < 0.42
        
    def should_pause_on_media(self) -> bool:
        """30% probability: pause on media without opening"""
        return random.random() < 0.30

    def should_ignore_last_5_messages(self) -> bool:
        """20% probability: ignore last 5 messages"""
        return random.random() < 0.20

    def should_ignore_older_than_2_min(self) -> bool:
        """15% probability: ignore messages >2 min old"""
        return random.random() < 0.15

    def should_skip_consecutive_sender(self) -> bool:
        """25% probability: skip consecutive sender blocks"""
        return random.random() < 0.25

    # Timing
    def get_compute_delay(self) -> float:
        """Add compute delay: 400-2200 ms (gamma jittered)"""
        # Gamma distribution: shape (k), scale (theta)
        # Mean = k * theta, Variance = k * theta^2
        shape = 2.0
        scale = 300 # Mean 600ms
        
        while True:
            delay_ms = np.random.gamma(shape, scale) + 400
            if 400 <= delay_ms <= 2200:
                return delay_ms / 1000.0

    def should_simulate_hover(self) -> bool:
        """Random hover before parse (p=0.46)"""
        return random.random() < 0.46

    def should_cancel_click(self) -> bool:
        """Random click cancel (p=0.12)"""
        return random.random() < 0.12

    # Exit behavior
    def should_idle_before_exit(self) -> bool:
        """40% probability: idle on chat list 2-9 sec before exit"""
        return random.random() < 0.40

    def get_idle_time(self) -> float:
        return random.uniform(2, 9)

    def should_instant_open_close(self) -> bool:
        """17% probability: open then instantly close a chat before exit"""
        return random.random() < 0.17

    def is_active_window(self) -> bool:
        """ACTIVE WINDOW: Start: 07:00, End: 23:00, Timezone: Local"""
        current_hour = datetime.now().hour
        return 7 <= current_hour < 23

    # Polling Params
    def generate_poll_params(self) -> dict:
        """
        Generate jittered time-window polling parameters.
        Replaces deterministic count-based retrieval.
        """
        import time
        now_ts = int(time.time())
        
        # time_to: now - random(2s, 12s)
        time_to = now_ts - random.randint(2, 12)
        
        # Determine time_window_size
        prob = random.random()
        if prob < 0.22:
            # Short window mode (240s - 420s)
            window_size = random.randint(240, 420)
        elif prob < 0.34: # 0.22 + 0.12 = 0.34
            # Extended curiosity mode (780s - 1200s)
            window_size = random.randint(780, 1200)
        else:
            # Normal window (420s - 780s)
            window_size = random.randint(420, 780)
            
        # Anti-pattern logic: Never repeat identical time_window_size consecutively
        while window_size == self.last_window_size:
            window_size = random.randint(420, 780) # Reroll normal if collision
        self.last_window_size = window_size
        
        time_from = time_to - window_size
        
        # Count parameter
        count = random.randint(5, 20)
        # Anti-pattern logic: Never reuse identical count consecutively
        while count == self.last_count:
            count = random.randint(5, 20)
        self.last_count = count
        
        # Offset rule
        offset = random.randint(0, 3) if random.random() < 0.25 else 0
        
        # Author filter probability
        use_author_filter = random.random() < 0.30
        
        params = {
            "time_from": time_from,
            "time_to": time_to,
            "count": count,
            "sort": "desc",
            "from_me": False,
            "normal_types": True,
            "offset": offset,
            "use_author_filter": use_author_filter
        }
        return params

    def get_processing_delay(self) -> float:
        """Add processing delay per message: random(400ms – 2200ms)"""
        return random.uniform(0.400, 2.200)

    def get_session_start_delay(self) -> float:
        """Do not poll immediately after session start: 3 - 15s delay"""
        return random.uniform(3.0, 15.0)
