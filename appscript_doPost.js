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
    usersSheet.appendRow([new Date(), d.name || '', d.email || '', d.password || '']);
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
  }

  // ── PASSWORD RESET ──────────────────────────────────────────────────
  if (d.action === 'resetPassword') {
    var email = (d.email || '').trim().toLowerCase();

    // Look up email in User Accounts sheet (column C)
    var usersSheet = ss.getSheetByName('User Accounts');
    var emailFound = false;
    if (usersSheet && email) {
      var data = usersSheet.getDataRange().getValues();
      for (var i = 1; i < data.length; i++) {
        if ((data[i][2] || '').trim().toLowerCase() === email) {
          emailFound = true;
          break;
        }
      }
    }

    if (emailFound) {
      // Generate 32-character hex token
      var token = '';
      var hexChars = '0123456789abcdef';
      for (var j = 0; j < 32; j++) {
        token += hexChars.charAt(Math.floor(Math.random() * 16));
      }

      // Store token in Password Resets sheet
      var resetSheet = ss.getSheetByName('Password Resets');
      if (!resetSheet) {
        resetSheet = ss.insertSheet('Password Resets');
        resetSheet.appendRow(['Timestamp', 'Email', 'Token', 'Expiry', 'Used']);
        resetSheet.setFrozenRows(1);
      }

      var now = new Date();
      var expiry = new Date(now.getTime() + 15 * 60 * 1000); // 15 minutes from now
      resetSheet.appendRow([now, email, token, expiry, false]);

      // Send reset email
      var resetLink = 'https://furever.home/reset?token=' + token;
      var subject = 'Furever Home - Password Reset Request';
      var body = 'Hello,\n\nYou requested a password reset for your Furever Home account.\n\n'
        + 'Click the link below to reset your password (expires in 15 minutes):\n'
        + resetLink + '\n\n'
        + 'If you did not request this, please ignore this email.\n\n'
        + 'Best regards,\nThe Furever Home Team';
      MailApp.sendEmail(email, subject, body);
    }

    // Always return ok regardless of whether email was found (prevent enumeration)
    return ContentService.createTextOutput(JSON.stringify({status:'ok'})).setMimeType(ContentService.MimeType.JSON);
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
