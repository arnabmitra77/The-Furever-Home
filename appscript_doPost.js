function doPost(e) {
  var ss = SpreadsheetApp.openById('1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80');
  var raw = (e.postData && e.postData.contents) ? e.postData.contents : '{}';
  var d = JSON.parse(raw);

  // ── LIKES TAB ──────────────────────────────────────────────────────
  if (d.action === 'like') {
    var likesSheet = ss.getSheetByName('Website Likes');
    if (!likesSheet) {
      likesSheet = ss.insertSheet('Website Likes');
      likesSheet.appendRow(['Timestamp', 'Action']);
      likesSheet.setFrozenRows(1);
    }
    likesSheet.appendRow([d.timestamp || new Date(), 'Like']);
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── USER ACCOUNTS TAB ──────────────────────────────────────────────
  if (d.action === 'signup') {
    var usersSheet = ss.getSheetByName('User Accounts');
    if (!usersSheet) {
      usersSheet = ss.insertSheet('User Accounts');
      usersSheet.appendRow(['Timestamp', 'Full Name', 'Email', 'Password (encoded)']);
      usersSheet.setFrozenRows(1);
    }
    // Check if email already exists (prevent duplicate accounts)
    var email = (d.email || '').trim().toLowerCase();
    var data = usersSheet.getDataRange().getValues();
    for (var i = 1; i < data.length; i++) {
      if ((data[i][2] || '').trim().toLowerCase() === email) {
        return ContentService.createTextOutput(JSON.stringify({status:'duplicate', message:'Email already registered'})).setMimeType(ContentService.MimeType.JSON);
      }
    }
    usersSheet.appendRow([new Date(), d.name || '', d.email || '', d.password || '']);
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── LOGIN VERIFICATION ────────────────────────────────────────────────
  if (d.action === 'login') {
    var usersSheet = ss.getSheetByName('User Accounts');
    if (!usersSheet) {
      return ContentService.createTextOutput(JSON.stringify({status:'error', message:'No accounts found'})).setMimeType(ContentService.MimeType.JSON);
    }
    var email = (d.email || '').trim().toLowerCase();
    var password = d.password || '';
    var data = usersSheet.getDataRange().getValues();
    for (var i = 1; i < data.length; i++) {
      if ((data[i][2] || '').trim().toLowerCase() === email && (data[i][3] || '') === password) {
        return ContentService.createTextOutput(JSON.stringify({status:'ok', name: data[i][1], email: data[i][2]})).setMimeType(ContentService.MimeType.JSON);
      }
    }
    return ContentService.createTextOutput(JSON.stringify({status:'error', message:'Invalid credentials'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── SHOWN INTEREST TAB ─────────────────────────────────────────────
  if (d.action === 'shownInterest') {
    var interestSheet = ss.getSheetByName('Shown Interest');
    if (!interestSheet) {
      interestSheet = ss.insertSheet('Shown Interest');
      interestSheet.appendRow(['Pet Name', 'Pet ID', 'Breed', 'Shelter Name', 'Shelter URL', 'Date', 'Time', 'User Name', 'User Email']);
      interestSheet.setFrozenRows(1);
    }
    interestSheet.appendRow([d.petName, d.petId, d.breed, d.shelterName, d.shelterUrl, d.date, d.time, d.userName, d.userEmail]);
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── ADOPTION INQUIRIES TAB ─────────────────────────────────────────
  var sheet = ss.getSheetByName('Inquiries');
  if (!sheet) {
    sheet = ss.insertSheet('Inquiries');
    sheet.appendRow(['Timestamp','Pet ID','Pet Name','Breed','Shelter','First Name','Last Name','Email','Phone','City','Housing Type','Pet Experience','Message']);
    sheet.setFrozenRows(1);
  }
  sheet.appendRow([new Date(), d.petId||'', d.petName||'', d.breed||'', d.shelter||'', d.firstName||'', d.lastName||'', d.email||'', d.phone||'', d.city||'', d.housing||'', d.experience||'', d.message||'']);
  return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
}
