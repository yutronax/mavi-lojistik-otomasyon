
import os

file_path = r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\src\fetchers\mavi_whap.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_until = -1

for i, line in enumerate(lines):
    if i <= skip_until:
        continue
    
    # Matching the problematic block around line 619
    if 'except Exception as chunk_error:' in line and 'error_str = str(chunk_error)' in lines[i+1]:
        new_lines.append('            except Exception as chunk_error:\n')
        new_lines.append('                error_str = str(chunk_error)\n')
        new_lines.append('                # Rate limit hatası -> otomatik key rotasyonu\n')
        new_lines.append('                if "RATE_LIMIT_ERROR" in error_str or "429" in error_str or "rate_limit" in error_str.lower():\n')
        new_lines.append('                    logger.warning(f"[Groq] Rate limit! Key rotasyonu yapılıyor...")\n')
        new_lines.append('                    if key_mgr.switch_to_next(reason="rate_limit_429"):\n')
        new_lines.append('                        new_key = key_mgr.get_active_key()\n')
        new_lines.append('                        client = OpenAI(base_url=base_url, api_key=new_key)\n')
        new_lines.append('                        logger.info(f"[Groq] Yeni key #{key_mgr.get_active_index()+1} aktif, chunk {idx+1} tekrar deneniyor...")\n')
        new_lines.append('                        try:\n')
        new_lines.append('                            chunk_shipments = _process_single_chunk(\n')
        new_lines.append('                                chunk, message_id, client, location_matcher, valid_iller, iller_listesi, model_name\n')
        new_lines.append('                            )\n')
        new_lines.append('                            if chunk_shipments:\n')
        new_lines.append('                                all_shipments.extend(chunk_shipments)\n')
        new_lines.append('                        except Exception as retry_err:\n')
        new_lines.append('                            logger.error(f"[Groq] Retry de başarısız: {retry_err}")\n')
        new_lines.append('                    else:\n')
        new_lines.append('                        logger.error("[Groq] Tüm API keyler tükendi!")\n')
        new_lines.append('                else:\n')
        new_lines.append('                    logger.error(f"[Groq] Parça {idx + 1} işlenirken hata: {chunk_error}")\n')
        
        # Skip the next 8 lines which are the original code block
        # (621 to 627 in my previous debug output)
        j = i + 2
        while j < len(lines) and (lines[j].strip().startswith('#') or 'RATE_LIMIT_ERROR' in lines[j] or 'logger.debug' in lines[j] or 'TODO' in lines[j] or 'else:' in lines[j] or 'logger.error' in lines[j]):
            if 'shipments_data =' in lines[j]: # Don't skip the next section
                break
            j += 1
        skip_until = j - 1
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("File updated successfully.")
