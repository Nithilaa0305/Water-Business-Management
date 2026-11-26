-- 02: users, sign-in sessions and the activity record
CREATE TABLE app_users (
    user_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    full_name varchar(150) NOT NULL,
    username varchar(50) NOT NULL UNIQUE,
    user_role varchar(20) NOT NULL,
    pin_hash text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_user_role CHECK (user_role IN ('owner', 'manager', 'employee'))
);

CREATE TABLE user_sessions (
    session_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES app_users(user_id),
    signed_in_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    signed_out_at timestamptz,
    sign_out_reason varchar(30),
    CONSTRAINT chk_sign_out_reason CHECK (sign_out_reason IS NULL OR sign_out_reason IN ('manual', 'auto', 'switched_user', 'new_sign_in'))
);

CREATE TABLE activity_log (
    activity_id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES app_users(user_id),
    session_id uuid REFERENCES user_sessions(session_id),
    action_time timestamptz NOT NULL DEFAULT clock_timestamp(),
    action_type varchar(50) NOT NULL,
    description text NOT NULL,
    reference_type varchar(50),
    reference_id uuid
);

-- nobody can change or delete the activity record
CREATE FUNCTION fn_activity_log_locked() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'The activity record cannot be changed or deleted';
    RETURN NULL;
END;
$$;

CREATE TRIGGER trg_activity_log_locked
    BEFORE UPDATE OR DELETE ON activity_log
    FOR EACH ROW EXECUTE FUNCTION fn_activity_log_locked();
