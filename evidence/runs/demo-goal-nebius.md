# Demo goal, end to end (Yang's laptop, 11 Oct 2026 00:50 IST)

Model: Nebius `Qwen/Qwen3-235B-A22B-Instruct-2507` (chain: nebius, then local Ollama; no other provider reachable).
Run time: 69 s from the request to S's final reply. Demo calls: 15 to Qwen3-235B (32,337 tokens in, 1,106 out). The startup model check also sent one tiny call each to DeepSeek-V4-Flash and local qwen3:4b.
One approval card (Desk: open the report) was approved; nothing else asked.

## Chat

**user** (+0 s, chat): Research the top 3 free LLM APIs for students, write a short report on the Desktop, open it, and remind me about it every Monday.

**s** (+9 s, handoff): @Scout Search for the top 3 free LLM APIs available for students. Include provider name, free tier details, and any usage limits or registration requirements.

**scout** (+36 s, chat): Top 3 free LLM APIs for students:  
  
- **Google Gemini API**    
  Free tier: Free input/output tokens on Gemini Flash and Gemini 1.5 Pro models.    
  Limits: Up to 1,500 requests/day and 1M tokens/minute (limits vary by project; check AI Studio).    
  Registration: Google account required; no credit card needed.    
  Source: [Google AI Studio](https://tokenmix.ai/blog/free-llm-api)  
  
- **Groq**    
  Free tier: Access to models like Llama 3.3 70B with OpenAI-compatible API.    
  Limits: 30 requests per minute, 1,000 requests/day, 200K tokens/day.    
  Registration: Free account required; no credit card.    
  Source: [Groq Rate Limits](https://tokenmix.ai/blog/free-llm-api)  
  
- **OpenRouter**    
  Free tier: Free access to select models (marked with :free).    
  Limits: 20 requests/minute, 50 free requests/day until $10 in credits is purchased.    
  Registration: Account required; no credit card for free tier.    
  Source: [OpenRouter Limits](https://tokenmix.ai/blog/free-llm-api)

**s** (+45 s, handoff): @Writer Write a short report titled 'Top 3 Free LLM APIs for Students' with the following content:  
  
1. Google Gemini API  
   - Free tier: Free input/output tokens on Gemini Flash and Gemini 1.5 Pro  
   - Limits: Up to 1,500 requests/day  
   - Registration: Google account, no credit card  
  
2. Groq  
   - Free tier: Access to Llama 3.3 70B and others  
   - Limits: 1,000 requests/day, 200K tokens/day  
   - Registration: Free account, no credit card  
  
3. OpenRouter  
   - Free tier: Free access to select models  
   - Limits: 50 free requests/day  
   - Registration: Account required, no credit card  
  
Save the report as 'Free_LLM_APIs_Report.txt' on the Desktop.

**writer** (+53 s, chat): Report saved as 'Free_LLM_APIs_Report.txt' on the Desktop.

**s** (+55 s, handoff): @Desk Open the file 'Free_LLM_APIs_Report.txt' on the Desktop.

**desk** (+65 s, chat): Opened Free_LLM_APIs_Report.txt in Notepad.

**s** (+69 s, chat): Report on the top 3 free LLM APIs for students has been created and opened on your Desktop.    
A reminder to review it will appear every Monday at 9 AM.    
Let me know if you'd like to adjust the reminder or the report.

## Result on the machine

- `Desktop\Free_LLM_APIs_Report.txt` written (536 bytes) and opened in Notepad after the card
- Routine: `every monday at 9am` -> "Remind me about the free LLM APIs report on the Desktop"

```
Top 3 Free LLM APIs for Students

1. Google Gemini API
   - Free tier: Free input/output tokens on Gemini Flash and Gemini 1.5 Pro
   - Limits: Up to 1,500 requests/day
   - Registration: Google account, no credit card

2. Groq
   - Free tier: Access to Llama 3.3 70B and others
   - Limits: 1,000 requests/day, 200K tokens/day
   - Registration: Free account, no credit card

3. OpenRouter
   - Free tier: Free access to select models
   - Limits: 50 free requests/day
   - Registration: Account required, no credit card
```
