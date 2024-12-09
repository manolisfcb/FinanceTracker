from marshmallow import Schema, fields


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str( required=True, load_only=True)
    
    class Meta:
        fields = ('name', 'email', 'password')
        

class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
    
    class Meta:
        fields = ('email', 'password')