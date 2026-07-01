function doPost(e) {
  var ss = SpreadsheetApp.openById('1Xg4T3vmhoLxN0C2lEBFaN88Y2LSvoF6DQVoCxL3dt80');
  var raw = (e.postData && e.postData.contents) ? e.postData.contents : '{}';
  var d = JSON.parse(raw);

  // ── LIKES ──────────────────────────────────────────────────────────
  if (d.action === 'like') {
    var likesSheet = getOrCreateSheet(ss, 'Website Likes', ['Timestamp', 'Action']);
    likesSheet.appendRow([d.timestamp || new Date(), 'Like']);
    return jsonResponse({status: 'ok'});
  }

  // ── GOOGLE SIGN-IN LOG ─────────────────────────────────────────────
  if (d.action === 'googleSignIn') {
    var usersSheet = getOrCreateSheet(ss, 'User Accounts', ['Timestamp', 'Full Name', 'Email', 'Sign-In Method']);
    var email = (d.email || '').trim().toLowerCase();
    var name = d.name || '';

    // Only add if user doesn't already exist
    if (!emailExists(usersSheet, email)) {
      usersSheet.appendRow([new Date(), name, email, 'Google']);
    }
    return jsonResponse({status: 'ok'});
  }

  // ── SHOWN INTEREST ─────────────────────────────────────────────────
  if (d.action === 'shownInterest') {
    var interestSheet = getOrCreateSheet(ss, 'Shown Interest', ['Pet Name', 'Pet ID', 'Breed', 'Shelter Name', 'Shelter URL', 'Date', 'Time', 'User Name', 'User Email']);
    interestSheet.appendRow([d.petName, d.petId, d.breed, d.shelterName, d.shelterUrl, d.date, d.time, d.userName, d.userEmail]);
    return jsonResponse({status: 'ok'});
  }

  // ── ADOPTION INQUIRIES (default) ───────────────────────────────────
  var sheet = getOrCreateSheet(ss, 'Inquiries', ['Timestamp','Pet ID','Pet Name','Breed','Shelter','First Name','Last Name','Email','Phone','City','Housing Type','Pet Experience','Message']);
  sheet.appendRow([new Date(), d.petId||'', d.petName||'', d.breed||'', d.shelter||'', d.firstName||'', d.lastName||'', d.email||'', d.phone||'', d.city||'', d.housing||'', d.experience||'', d.message||'']);
  return jsonResponse({status: 'ok'});
}

// ── HELPERS ────────────────────────────────────────────────────────────────

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function getOrCreateSheet(ss, name, headers) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
    sheet.appendRow(headers);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function emailExists(sheet, email) {
  if (!email) return false;
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if ((data[i][2] || '').trim().toLowerCase() === email) {
      return true;
    }
  }
  return false;
}
