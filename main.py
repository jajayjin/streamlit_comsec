import streamlit as st
import pandas as pd
import json
import streamlit.components.v1 as components
import pickle

st.title("🔐 Keystroke Dynamics Authentication")

st.markdown("""
Type the password into the field below. This will record:
- **Dwell time** (how long each key is held)
- **Flight time** (gap between keys)

Press **Enter** to finish a sample.
""")

# Initialize state
if "samples" not in st.session_state:
    st.session_state.samples = []
if "sample_number" not in st.session_state:
    st.session_state.sample_number = 1

user_id = st.text_input("User ID", value="user_Test")
password_ref = st.text_input("Reference Password", value="ict555")

# JavaScript to record key events
components.html("""
<div>
    <input id="typingField" placeholder="Type password and press Enter" style="width: 100%; padding: 10px; font-size: 18px;" autofocus />
</div>
<script>
    const field = document.getElementById("typingField");
    let events = [];

    field.addEventListener("keydown", (e) => {
        const now = Date.now();
        events.push({
            key: e.key,
            type: "down",
            time: now
        });
    });

    field.addEventListener("keyup", (e) => {
        const now = Date.now();
        events.push({
            key: e.key,
            type: "up",
            time: now
        });

        // When Enter is pressed, save & copy JSON
        if (e.key === "Enter") {
            try {
                const data = JSON.stringify(events, null, 2);

                // Create a temporary textarea to hold the JSON
                const textarea = document.createElement("textarea");
                textarea.value = data;
                document.body.appendChild(textarea);
                textarea.select();

                // Execute copy command
                document.execCommand("copy");

                // Clean up by removing the textarea
                document.body.removeChild(textarea);

                alert("✅ Sample captured and copied to clipboard.\\n\\nNow paste it into the Streamlit app.");
                field.value = "";
                events = [];
            } catch (err) {
                alert("❌ Failed to copy keystroke data: " + err.message);
            }
        }
    });
</script>
""", height=180)

# Paste data from clipboard into text box
raw_json = st.text_area("Paste Captured JSON Here After Typing", height=150)

if st.button("Submit"):
    if not user_id or not password_ref:
        st.error("Please enter both User ID and Reference Password.")
    elif not raw_json:
        st.warning("Paste JSON data from browser popup first.")
    else:
        try:
            key_events = json.loads(raw_json)
            keydowns = []
            keyups = []
            typed_password = "" #Store the typed password.
            for e in key_events:
                if e["type"] == "down":
                    keydowns.append((e["key"], e["time"]))
                elif e["type"] == "up":
                    keyups.append((e["key"], e["time"]))
                    if e['key'] != "Enter":
                        typed_password += e['key'] #Append the character to the typed password.

            if len(keydowns) != len(password_ref) + 1 or len(keyups) != len(password_ref) + 1:
                st.error("Typed password doesn't match reference length (including Enter).")
            elif typed_password != password_ref: #Check if passwords match.
                st.error("Incorrect password.")
            else:
                sample = {
                    "user_id": user_id,
                    "password": password_ref,
                    "sample_number": st.session_state.sample_number
                }

                dwell_times = [keyups[i][1] - keydowns[i][1] for i in range(len(password_ref))]
                flight_times = [keydowns[i][1] - keyups[i - 1][1] for i in range(1, len(password_ref))]
                flight_times.append(keydowns[-1][1] - keyups[-2][1])  # Add the final flight time.
                dwell_times.append(keyups[-1][1] - keydowns[-1][1]) #Add the dwell time of the enter key.

                for i, d in enumerate(dwell_times):
                    sample[f"dwell_{i}"] = int(d)
                for i, f in enumerate(flight_times):
                    sample[f"flight_{i}"] = int(f)

                st.session_state.samples.append(sample)
                # st.success(f"✅ Sample #{st.session_state.sample_number} recorded.")
                st.session_state.sample_number += 1

                df = pd.DataFrame(st.session_state.samples)

                with open('comsec_model_final.pkl', 'rb') as f:
                    model = pickle.load(f)
                st.dataframe(df)

                df['total_time'] = df[[f'dwell_{i}' for i in range(7)] + [f'flight_{i}' for i in range(6)]].sum(axis=1)
                df['mean_dwell'] = df[[f'dwell_{i}' for i in range(7)]].mean(axis=1)
                df['std_dwell'] = df[[f'dwell_{i}' for i in range(7)]].std(axis=1)
                df['mean_flight'] = df[[f'flight_{i}' for i in range(6)]].mean(axis=1)
                df['std_flight'] = df[[f'flight_{i}' for i in range(6)]].std(axis=1)
                for i in range(6):
                    df[f'dwell_to_flight_ratio_{i}'] = df[f'dwell_{i}'] / (df[f'flight_{i}'] + 1e-5)
                for col in [f'dwell_{i}' for i in range(7)] + [f'flight_{i}' for i in range(6)]:
                    df[f'{col}_norm'] = df[col] / (df['total_time'] + 1e-5)

                test_dfs = df.sample(frac=1)
                testfeatures = [col for col in test_dfs.columns if 'norm' in col]
                X_test2 = test_dfs[testfeatures]
                y_test2 = test_dfs['password']

                y_pred_test = model.predict_proba(X_test2)
                positive_probs_test = y_pred_test[:, 1]

                threshold = 0.8
                y_preds_test = (positive_probs_test >= threshold).astype(int)

                if y_preds_test[0] == 1:
                    page_file = "pages/login_success.py"
                    st.switch_page(page_file)
                else:
                    page_file = "pages/login_fail.py"
                    st.switch_page(page_file)

        except Exception as e:
            st.error(f"Error parsing input: {e}")