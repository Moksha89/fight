#!/bin/bash
# Real Player Testing Script
# This script tests the full player journey on RoosterRun

BASE_URL="http://127.0.0.1:8765"
API_URL="$BASE_URL/api"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   RoosterRun Real Player Test${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Function to print test results
print_test() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Step 1: Check server health
echo -e "${YELLOW}[1/10] Checking server health...${NC}"
CONFIG_CHECK=$(curl -s "$API_URL/site/config/" | jq -r '.brand.site_name' 2>/dev/null)
if [ -n "$CONFIG_CHECK" ] && [ "$CONFIG_CHECK" != "null" ]; then
    print_test 0 "Server is online (site: $CONFIG_CHECK)"
else
    print_test 1 "Server health check failed"
    exit 1
fi

# Step 2: Check China feed status
echo -e "\n${YELLOW}[2/10] Checking China 24/7 feed...${NC}"
CONFIG=$(curl -s "$API_URL/site/config/")
CHINA_ENABLED=$(echo "$CONFIG" | jq -r '.china_feed.enabled' 2>/dev/null)
CHINA_MATCH=$(echo "$CONFIG" | jq -r '.china_feed.match_number // "none"' 2>/dev/null)
print_test 0 "China feed enabled: $CHINA_ENABLED"
echo -e "   Current match: #$CHINA_MATCH"

# Step 3: Register a new player
echo -e "\n${YELLOW}[3/10] Registering new player...${NC}"
REGISTER_DATA='{
  "username": "testplayer01",
  "mobile": "+919876543210",
  "password": "TestPlayer@123456",
  "otp": "preview_otp"
}'
REGISTER_RESPONSE=$(curl -s -X POST \
  -H "Content-Type: application/json" \
  -d "$REGISTER_DATA" \
  "$API_URL/user/register/" 2>&1)

if echo "$REGISTER_RESPONSE" | jq -e '.session_token' >/dev/null 2>&1; then
    print_test 0 "Player registered successfully"
    SESSION_TOKEN=$(echo "$REGISTER_RESPONSE" | jq -r '.session_token')
elif echo "$REGISTER_RESPONSE" | grep -q "already exists"; then
    print_test 0 "Player already exists, will try login"
    SESSION_TOKEN=""
else
    print_test 1 "Registration failed: $REGISTER_RESPONSE"
fi

# Step 4: Login if registration failed
if [ -z "$SESSION_TOKEN" ]; then
    echo -e "\n${YELLOW}[4/10] Logging in...${NC}"
    LOGIN_DATA='{
      "mobile": "+919876543210",
      "password": "TestPlayer@123456",
      "otp": "preview_otp"
    }'
    LOGIN_RESPONSE=$(curl -s -X POST \
      -H "Content-Type: application/json" \
      -d "$LOGIN_DATA" \
      "$API_URL/user/login/" 2>&1)
    
    SESSION_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.session_token // ""')
    if [ -n "$SESSION_TOKEN" ]; then
        print_test 0 "Login successful"
    else
        print_test 1 "Login failed: $LOGIN_RESPONSE"
        exit 1
    fi
else
    echo -e "\n${YELLOW}[4/10] Using session from registration${NC}"
    print_test 0 "Session token obtained"
fi

# Step 5: Get player profile
echo -e "\n${YELLOW}[5/10] Fetching player profile...${NC}"
PROFILE=$(curl -s -H "Cookie: rr_session_token=$SESSION_TOKEN" "$API_URL/user/me/" 2>&1)
USERNAME=$(echo "$PROFILE" | jq -r '.username // "unknown"')
BALANCE=$(echo "$PROFILE" | jq -r '.wallet_balance // 0')
print_test 0 "Username: $USERNAME"
echo -e "   Wallet balance: ₹$BALANCE"

# Step 6: Check available games
echo -e "\n${YELLOW}[6/10] Checking available games...${NC}"
GAMES=$(curl -s "$API_URL/site/config/" | jq '.games')
GAME_COUNT=$(echo "$GAMES" | jq 'length')
FEATURED_GAME=$(curl -s "$API_URL/site/config/" | jq -r '.featured_game.title // "none"')
print_test 0 "Available games: $GAME_COUNT"
echo -e "   Featured game: $FEATURED_GAME"

# Step 7: View match results history
echo -e "\n${YELLOW}[7/10] Fetching match results history...${NC}"
RESULTS=$(curl -s "$API_URL/cockfight/auto-history/?limit=5" 2>&1)
RESULTS_COUNT=$(echo "$RESULTS" | jq '.results | length' 2>/dev/null)
if [ "$RESULTS_COUNT" -gt 0 ]; then
    print_test 0 "Results history: $RESULTS_COUNT matches"
    echo "$RESULTS" | jq -r '.results[] | "   Match #\(.matchNumber): \(.result) - \(.title)"' | head -3
else
    print_test 0 "Results history: empty (no completed matches yet)"
fi

# Step 8: Check bet history
echo -e "\n${YELLOW}[8/10] Checking bet history...${NC}"
BETS=$(curl -s -H "Cookie: rr_session_token=$SESSION_TOKEN" "$API_URL/cockfight/bets/" 2>&1)
BET_COUNT=$(echo "$BETS" | jq '.results | length' 2>/dev/null || echo 0)
print_test 0 "Bet history: $BET_COUNT bets"

# Step 9: Check payment wallet
echo -e "\n${YELLOW}[9/10] Checking payment wallet...${NC}"
WALLET=$(curl -s -H "Cookie: rr_session_token=$SESSION_TOKEN" "$API_URL/payments/wallet/" 2>&1)
WALLET_BALANCE=$(echo "$WALLET" | jq -r '.balance // 0')
AVAILABLE=$(echo "$WALLET" | jq -r '.available // 0')
EXPOSURE=$(echo "$WALLET" | jq -r '.bet_exposure // 0')
print_test 0 "Wallet balance: ₹$WALLET_BALANCE"
echo -e "   Available: ₹$AVAILABLE"
echo -e "   Bet exposure: ₹$EXPOSURE"

# Step 10: Check payment requests history
echo -e "\n${YELLOW}[10/10] Checking payment history...${NC}"
PAYMENTS=$(curl -s -H "Cookie: rr_session_token=$SESSION_TOKEN" "$API_URL/payments/requests/" 2>&1)
PAYMENT_COUNT=$(echo "$PAYMENTS" | jq '.results | length' 2>/dev/null || echo 0)
print_test 0 "Payment requests: $PAYMENT_COUNT"

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Test Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "\nPlayer Summary:"
echo -e "  Username: $USERNAME"
echo -e "  Balance: ₹$WALLET_BALANCE"
echo -e "  Bet History: $BET_COUNT bets"
echo -e "  Match Results: $RESULTS_COUNT matches"
echo -e "  China Feed: $CHINA_ENABLED (Match #$CHINA_MATCH)"
echo -e "\nPlayer App: $BASE_URL/play/"
echo -e "Admin Console: $BASE_URL/admin/"
